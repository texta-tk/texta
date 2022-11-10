import json
import logging
import os
import pathlib
import secrets
from typing import Dict, List, Union

from celery import group, chain
from celery.decorators import task
from celery.result import allow_join_result
from django.conf import settings
from elasticsearch.helpers import streaming_bulk
from minio.error import MinioException
from texta_elastic.core import ElasticCore
from texta_elastic.document import ElasticDocument
from texta_elastic.query import Query
from texta_elastic.searcher import ElasticSearcher
from texta_embedding.embedding import W2VEmbedding
from texta_tagger.tagger import Tagger as TextTagger

from toolkit.base_tasks import BaseTask, TransactionAwareTask
from toolkit.core.task.models import Task
from toolkit.elastic.tools.data_sample import DataSample
from toolkit.embedding.models import Embedding
from toolkit.helper_functions import add_finite_url_to_feedback, get_indices_from_object, load_stop_words
from toolkit.mlp.tasks import apply_mlp_on_list
from toolkit.tagger.models import Tagger, TaggerGroup
from toolkit.tools.plots import create_tagger_plot
from toolkit.tools.show_progress import ShowProgress


def prepare_tagger_objects(tg: TaggerGroup, tags: List[str], tagger_serializer: dict, tag_queries: List[dict]) -> List[int]:
    """
    Task for creating Tagger objects inside Tagger Group to prevent database timeouts.
    :param tagger_serializer: Dictionary representation of to-be-trained Taggers common fields.
    :param tags: Which tags to train on.
    :param tag_queries: List of Elasticsearch queries for every tag.
    """
    # create tagger objects
    logger = logging.getLogger(settings.INFO_LOGGER)
    logger.info(f"[Tagger Group] Starting task 'create_tagger_objects' for TaggerGroup with ID: {tg.pk}!")
    tagger_ids = []

    taggers_to_create = []
    for i, tag in enumerate(tags):
        tagger_data = tagger_serializer.copy()
        tagger_data.update({"query": json.dumps(tag_queries[i], ensure_ascii=False)})
        tagger_data.update({"description": tag})
        tagger_data.update({"fields": json.dumps(tagger_data["fields"])}),
        tagger_data.update({"stop_words": json.dumps(tagger_data["stop_words"], ensure_ascii=False)})
        taggers_to_create.append(tagger_data)

        indices = [index["name"] for index in tagger_data["indices"]]
        indices = tg.project.get_available_or_all_project_indices(indices)
        tagger_data.pop("indices")

        embedding_id = tagger_data.get("embedding", None)
        if embedding_id:
            tagger_data["embedding"] = Embedding.objects.get(pk=embedding_id)

        tagger_group_info = [
            {
                "description": tg.description,
                "id": tg.pk,
                "fact_name": tg.fact_name
            }
        ]

        tagger_data["tagger_groups"] = json.dumps(tagger_group_info)

        created_tagger = Tagger.objects.create(
            **tagger_data,
            author=tg.author,
            project=tg.project,
        )

        task_object = Task.objects.create(task_type=Task.TYPE_TRAIN, status=Task.STATUS_CREATED)
        created_tagger.tasks.add(task_object)

        from toolkit.elastic.index.models import Index
        for index in Index.objects.filter(name__in=indices, is_open=True):
            created_tagger.indices.add(index)

        # add and save
        tg.taggers.add(created_tagger)
        tg.save()

        tagger_ids.append(created_tagger.pk)

    return tagger_ids


@task(name="start_tagger_group", base=TransactionAwareTask, queue=settings.CELERY_LONG_TERM_TASK_QUEUE)
def start_tagger_group(tagger_group_id: int, tags, tagger_serializer, tag_queries):
    tg = TaggerGroup.objects.get(pk=tagger_group_id)
    task_object = Task.objects.create(taggergroup=tg, task_type=Task.TYPE_TRAIN, status=Task.STATUS_RUNNING)
    tg.tasks.add(task_object)

    try:
        tagger_ids = prepare_tagger_objects(tg, tags, tagger_serializer, tag_queries)

        tasks = []
        for tagger_pk in tagger_ids:
            task_chain = start_tagger_task.s(tagger_pk) | train_tagger_task.s() | save_tagger_results.s()
            tasks.append(task_chain)

        # Create the chord.
        task = chain(group(tasks), end_tagger_group.s(tagger_group_id=tg.pk))

        # Put it into a transaction to ensure the task objects are created and accessible.
        from django.db import transaction
        transaction.on_commit(lambda: task.apply_async(queue=settings.CELERY_LONG_TERM_TASK_QUEUE))
    except Exception as e:
        task_object.handle_failed_task(e)


@task(name="start_tagger_task", base=TransactionAwareTask, queue=settings.CELERY_LONG_TERM_TASK_QUEUE)
def start_tagger_task(tagger_id: int):
    tagger = Tagger.objects.get(pk=tagger_id)
    task_object = tagger.tasks.last()
    show_progress = ShowProgress(task_object, multiplier=1)
    show_progress.update_step('starting tagging')
    show_progress.update_view(0)
    return tagger_id


@task(name="train_tagger_task", base=TransactionAwareTask, queue=settings.CELERY_LONG_TERM_TASK_QUEUE)
def train_tagger_task(tagger_id: int):
    info_logger = logging.getLogger(settings.INFO_LOGGER)

    info_logger.info(f"[Tagger] Starting task 'train_tagger' for tagger with ID: {tagger_id}!")
    tagger_object = Tagger.objects.get(id=tagger_id)
    task_object = tagger_object.tasks.last()

    try:
        # create progress object
        show_progress = ShowProgress(task_object, multiplier=1)
        show_progress.update_step('scrolling positives')
        show_progress.update_view(0)

        # retrieve indices & field data
        indices = get_indices_from_object(tagger_object)
        field_data = json.loads(tagger_object.fields)
        # split stop words by space or newline and remove empties

        stop_words = load_stop_words(tagger_object.stop_words)
        ignore_numbers = tagger_object.ignore_numbers

        # get scoring function
        if tagger_object.scoring_function != "default":
            scoring_function = tagger_object.scoring_function
        else:
            scoring_function = None

        info_logger.info(f"[Tagger] Using scoring function: {scoring_function}.")

        # load embedding if any
        if tagger_object.embedding:
            embedding = W2VEmbedding()
            embedding.load_django(tagger_object.embedding)
        else:
            embedding = None
        # create Datasample object for retrieving positive and negative sample
        data_sample = DataSample(
            tagger_object,
            indices=indices,
            field_data=field_data,
            show_progress=show_progress,
            snowball_language=tagger_object.snowball_language,
            detect_lang=tagger_object.detect_lang,
            balance=tagger_object.balance,
            balance_to_max_limit=tagger_object.balance_to_max_limit
        )
        # update status to training
        show_progress.update_step("training")
        show_progress.update_view(0)
        # train model
        tagger = TextTagger(
            embedding=embedding,
            custom_stop_words=stop_words,
            ignore_numbers=ignore_numbers,
            classifier=tagger_object.classifier,
            vectorizer=tagger_object.vectorizer,
            analyzer=tagger_object.analyzer
        )
        tagger.train(
            data_sample.data,
            pos_label=tagger_object.pos_label,
            field_list=field_data,
            scoring=scoring_function
        )

        # save tagger to disk
        tagger_full_path, relative_tagger_path = tagger_object.generate_name("tagger")
        tagger.save(tagger_full_path)

        # Save the image before its path.
        image_name = f'{secrets.token_hex(15)}.png'
        tagger_object.plot.save(image_name, create_tagger_plot(tagger.report.to_dict()), save=False)
        image_path = pathlib.Path(settings.MEDIA_URL) / image_name

        # get num examples
        num_examples = {k: len(v) for k, v in data_sample.data.items()}

        return {
            "id": tagger_id,
            "tagger_path": relative_tagger_path,
            "precision": float(tagger.report.precision),
            "recall": float(tagger.report.recall),
            "f1_score": float(tagger.report.f1_score),
            "num_features": tagger.report.num_features,
            "num_examples": num_examples,
            "confusion_matrix": tagger.report.confusion.tolist(),
            "model_size": round(float(os.path.getsize(tagger_full_path)) / 1000000, 1),  # bytes to mb
            "plot": str(image_path),
            "classes": tagger.report.classes
        }


    except Exception as e:
        task_object.handle_failed_task(e)
        raise e

# S3 for Taggers

@task(name="download_tagger_model", base=TransactionAwareTask, queue=settings.CELERY_LONG_TERM_TASK_QUEUE)
def download_tagger_model(minio_path: str, user_pk: int, project_pk: int, version_id: str):
    info_logger = logging.getLogger(settings.INFO_LOGGER)
    info_logger.info(f"[Tagger] Starting to download model from Minio with path {minio_path}!")
    tagger_pk = Tagger.download_from_s3(minio_path, user_pk=user_pk, project_pk=project_pk, version_id=version_id)
    info_logger.info(f"[Tagger] Finished to download model from Minio with path {minio_path}!")
    return tagger_pk


@task(name="download_into_tagger_group", base=TransactionAwareTask, queue=settings.CELERY_LONG_TERM_TASK_QUEUE)
def download_into_tagger_group(tagger_group_pk: int, minio_path: str, version_id: str):
    info_logger = logging.getLogger(settings.INFO_LOGGER)
    info_logger.info(f"[Tagger Group] Starting to download model from Minio with path {minio_path}!")
    tg = TaggerGroup.objects.get(pk=tagger_group_pk)
    tg.add_from_s3(minio_path, tg.author.pk, version_id)
    info_logger.info(f"[Tagger Group] Finished to download model from Minio with path {minio_path}!")


@task(name="upload_tagger_files", base=TransactionAwareTask, queue=settings.CELERY_LONG_TERM_TASK_QUEUE)
def upload_tagger_files(tagger_id: int, minio_path: str):
    tagger = Tagger.objects.get(pk=tagger_id)
    task_object: Task = tagger.tasks.last()
    info_logger = logging.getLogger(settings.INFO_LOGGER)

    task_object.update_status(Task.STATUS_RUNNING)
    task_object.step = "uploading into S3"
    task_object.save()

    try:
        info_logger.info(f"[Tagger] Starting to upload tagger with ID {tagger_id} into S3!")
        minio_path = minio_path if minio_path else tagger.generate_s3_location()
        data = tagger.export_resources()
        tagger.upload_into_s3(minio_path=minio_path, data=data)
        info_logger.info(f"[Tagger] Finished upload of tagger with ID {tagger_id} into S3!")
        task_object.complete()

    except MinioException as e:
        task_object.handle_failed_task(f"Could not connect to S3, are you using the right credentials?")
        raise e

    except Exception as e:
        task_object.handle_failed_task(e)
        raise e

### S3 for Tagger Groups

@task(name="download_tagger_group_models", base=TransactionAwareTask, queue=settings.CELERY_LONG_TERM_TASK_QUEUE)
def download_tagger_group_models(minio_path: str, user_pk: int, project_pk: int, version_id: str):
    info_logger = logging.getLogger(settings.INFO_LOGGER)
    info_logger.info(f"[Tagger Group] Starting to download model from Minio with path {minio_path}!")
    tagger_pk = TaggerGroup.download_from_s3(minio_path, user_pk=user_pk, project_pk=project_pk, version_id=version_id)
    info_logger.info(f"[Tagger Group] Finished to download model from Minio with path {minio_path}!")
    return tagger_pk


@task(name="upload_tagger_group_files", base=TransactionAwareTask, queue=settings.CELERY_LONG_TERM_TASK_QUEUE)
def upload_tagger_group_files(tagger_id: int, minio_path: str):
    tagger = TaggerGroup.objects.get(pk=tagger_id)
    task_object: Task = tagger.tasks.last()
    info_logger = logging.getLogger(settings.INFO_LOGGER)

    task_object.update_status(Task.STATUS_RUNNING)
    task_object.step = "uploading into S3"
    task_object.save()

    try:
        info_logger.info(f"[Tagger Group] Starting to upload tagger with ID {tagger_id} into S3!")
        minio_path = minio_path if minio_path else tagger.generate_s3_location()
        data = tagger.export_resources()
        tagger.upload_into_s3(minio_path=minio_path, data=data)
        info_logger.info(f"[Tagger Group] Finished upload of tagger with ID {tagger_id} into S3!")
        task_object.complete()

    except MinioException as e:
        task_object.handle_failed_task(f"Could not connect to S3, are you using the right credentials?")
        raise e

    except Exception as e:
        task_object.handle_failed_task(e)
        raise e


@task(name="save_tagger_results", base=TransactionAwareTask, queue=settings.CELERY_LONG_TERM_TASK_QUEUE)
def save_tagger_results(result_data: dict):
    try:
        tagger_id = result_data['id']
        info_logger = logging.getLogger(settings.INFO_LOGGER)

        info_logger.info(f"[Tagger] Saving task results for tagger with ID: {tagger_id}!")
        tagger_object = Tagger.objects.get(pk=tagger_id)

        # Handle previous tagger models that exist in case of retrains.
        model_path = pathlib.Path(tagger_object.model.path) if tagger_object.model else None

        task_object = tagger_object.tasks.last()
        show_progress = ShowProgress(task_object, multiplier=1)
        # update status to saving
        show_progress.update_step('saving')
        show_progress.update_view(0)
        tagger_object.model.name = result_data["tagger_path"]
        tagger_object.precision = result_data["precision"]
        tagger_object.recall = result_data["recall"]
        tagger_object.f1_score = result_data["f1_score"]
        tagger_object.num_features = result_data["num_features"]
        tagger_object.num_examples = json.dumps(result_data["num_examples"])
        tagger_object.model_size = result_data["model_size"]
        tagger_object.plot.name = result_data["plot"]
        tagger_object.confusion_matrix = result_data["confusion_matrix"]
        tagger_object.classes = json.dumps(result_data["classes"], ensure_ascii=False)
        tagger_object.save()
        task_object.complete()

        # Cleanup after the transaction to ensure integrity database records.
        if model_path and model_path.exists():
            model_path.unlink(missing_ok=True)

    # Here the exception is handled instead of reraised to avoid causing trouble when training Tagger Groups as they use Celery chords.
    except Exception as e:
        task_object.handle_failed_task(e)


def get_mlp(tagger_group_id: int, text: str, lemmatize: bool = False, use_ner: bool = True):
    """
    Retrieves lemmas.
    Retrieves tags predicted by MLP NER and present in models.
    :return: string, list
    """
    tags = []
    hybrid_tagger_object = TaggerGroup.objects.get(pk=tagger_group_id)

    taggers = {t.description.lower(): {"tag": t.description, "id": t.id} for t in hybrid_tagger_object.taggers.all()}

    if lemmatize or use_ner:
        logging.getLogger(settings.INFO_LOGGER).info(f"[Get MLP] Applying lemmatization and NER...")
        with allow_join_result():
            mlp = apply_mlp_on_list.apply_async(kwargs={"texts": [text], "analyzers": ["all"]}, queue=settings.CELERY_MLP_TASK_QUEUE).get()
            mlp_result = mlp[0]
            logging.getLogger(settings.INFO_LOGGER).info(f"[Get MLP] Finished applying MLP.")

    # lemmatize
    if lemmatize and mlp_result:
        text = mlp_result["text_mlp"]["lemmas"]
        lemmas_exists = True if text.strip() else False
        logging.getLogger(settings.INFO_LOGGER).info(f"[Get MLP] Lemmatization result exists: {lemmas_exists}")

    # retrieve tags
    if use_ner and mlp_result:
        seen_tags = {}
        for fact in mlp_result["texta_facts"]:
            fact_val = fact["str_val"].lower().strip()
            if fact_val in taggers and fact_val not in seen_tags:
                fact_val_dict = {
                    "tag": taggers[fact_val]["tag"],
                    "probability": 1.0,
                    "tagger_id": taggers[fact_val]["id"],
                    "ner_match": True
                }
                tags.append(fact_val_dict)
                seen_tags[fact_val] = True
        logging.getLogger(settings.INFO_LOGGER).info(f"[Get MLP] Detected {len(tags)} with NER.")

    return text, tags


def get_tag_candidates(tagger_group_id: int, text: str, ignore_tags: List[str] = [], n_similar_docs: int = 10, max_candidates: int = 10):
    """
    Finds frequent tags from documents similar to input document.
    Returns empty list if hybrid option false.
    """
    hybrid_tagger_object = TaggerGroup.objects.get(pk=tagger_group_id)
    field_paths = json.loads(hybrid_tagger_object.taggers.first().fields)
    indices = hybrid_tagger_object.get_indices()
    info_logger = logging.getLogger(settings.INFO_LOGGER)

    info_logger.info(f"[Get Tag Candidates] Selecting from following indices: {indices}.")
    ignore_tags = {tag["tag"]: True for tag in ignore_tags}
    # create query
    query = Query()
    query.add_mlt(field_paths, text)
    # create Searcher object for MLT
    es_s = ElasticSearcher(indices=indices, query=query.query)
    info_logger.info(f"[Get Tag Candidates] Trying to retrieve {n_similar_docs} documents from Elastic...")
    docs = es_s.search(size=n_similar_docs)
    info_logger.info(f"[Get Tag Candidates] Successfully retrieved {len(docs)} documents from Elastic.")
    # dict for tag candidates from elastic
    tag_candidates = {}
    # retrieve tags from elastic response
    for doc in docs:
        if "texta_facts" in doc:
            for fact in doc["texta_facts"]:
                if fact["fact"] == hybrid_tagger_object.fact_name:
                    fact_val = fact["str_val"]
                    if fact_val not in ignore_tags:
                        if fact_val not in tag_candidates:
                            tag_candidates[fact_val] = 0
                        tag_candidates[fact_val] += 1
    # sort and limit candidates
    tag_candidates = [item[0] for item in sorted(tag_candidates.items(), key=lambda k: k[1], reverse=True)][:max_candidates]
    info_logger.info(f"[Get Tag Candidates] Retrieved {len(tag_candidates)} tag candidates.")
    return tag_candidates


@task(name="apply_tagger", base=BaseTask)
def apply_tagger(tagger_id: int, content: Union[str, Dict[str, str]], input_type='text', lemmatize=False, feedback=None, use_logger=True):
    """Task for applying tagger to text. Wraps functions load_tagger and apply_loaded_tagger."""
    if use_logger:
        logging.getLogger(settings.INFO_LOGGER).info(
            f"Starting task 'apply_tagger' for tagger with ID: {tagger_id} with params (input_type : {input_type}, lemmatize: {lemmatize}, feedback: {feedback})!")

    tagger_object = Tagger.objects.get(pk=tagger_id)

    # Load tagger model from the disc
    tagger = tagger_object.load_tagger(lemmatize=lemmatize)

    # Use the loaded model for predicting
    prediction = tagger_object.apply_loaded_tagger(tagger=tagger, content=content, input_type=input_type, feedback=feedback)

    return prediction


def apply_tagger_group(tagger_group_id: int, content: Union[str, Dict[str, str]], tag_candidates: List[str], request, input_type: str = 'text', lemmatize: bool = False,
                       feedback: bool = False, use_async: bool = True):
    # get tagger group object
    logging.getLogger(settings.INFO_LOGGER).info(f"[Apply Tagger Group] Starting apply_tagger_group...")
    tagger_group_object = TaggerGroup.objects.get(pk=tagger_group_id)
    # get tagger objects
    candidates_str = "|".join(tag_candidates)
    tagger_objects = tagger_group_object.taggers.filter(description__iregex=f"^({candidates_str})$")
    # filter out completed
    tagger_objects = [tagger for tagger in tagger_objects if tagger.tasks.last().status == Task.STATUS_COMPLETED]
    logging.getLogger(settings.INFO_LOGGER).info(f"[Apply Tagger Group] Loaded {len(tagger_objects)} tagger objects.")
    # predict tags
    if use_async:
        with allow_join_result():
            group_task = group(apply_tagger.s(tagger.pk, content, input_type=input_type, lemmatize=lemmatize, feedback=feedback, use_logger=False) for tagger in tagger_objects)
            group_results = group_task.apply_async(queue=settings.CELERY_SHORT_TERM_TASK_QUEUE)
            result_tags = group_results.get()

            logging.getLogger(settings.INFO_LOGGER).info(f"[Apply Tagger Group] Group task applied.")

    else:
        result_tags = []
        for tagger in tagger_objects:
            result = apply_tagger(tagger.pk, content, input_type=input_type, lemmatize=lemmatize, feedback=feedback, use_logger=False)
            result_tags.append(result)

    # retrieve results & remove non-hits
    tags = [tag for tag in result_tags if tag]

    logging.getLogger(settings.INFO_LOGGER).info(f"[Apply Tagger Group] Retrieved results for {len(tags)} taggers.")
    # remove non-hits
    tags = [tag for tag in tags if tag["result"]]

    logging.getLogger(settings.INFO_LOGGER).info(f"[Apply Tagger Group] Retrieved {len(tags)} positive tags.")
    # if feedback was enabled, add urls
    if feedback:
        tags = [add_finite_url_to_feedback(tag, request) for tag in tags]
    # sort by probability and return
    return sorted(tags, key=lambda k: k["probability"], reverse=True)


def to_texta_fact(tagger_result: List[Dict[str, Union[str, int, bool]]], field: str, fact_name: str, fact_value: str):
    new_facts = []
    for result in tagger_result:
        if result["result"]:
            str_val = fact_value if fact_value else result["tag"]
            new_fact = {
                "fact": fact_name,
                "str_val": str_val,
                "doc_path": field,
                "spans": json.dumps([[0, 0]])
            }
            new_facts.append(new_fact)
    return new_facts


def update_generator(generator: ElasticSearcher, ec: ElasticCore, fields: List[str], fact_name: str, fact_value: str, max_tags: int, object_id: int, object_type: str,
                     tagger_object: Union[Tagger, TaggerGroup], object_args: Dict, tagger: TextTagger = None):
    for i, scroll_batch in enumerate(generator):
        logging.getLogger(settings.INFO_LOGGER).info(f"[Tagger] Appyling {object_type} with ID {object_id} to batch {i + 1}...")
        for raw_doc in scroll_batch:
            hit = raw_doc["_source"]
            flat_hit = ec.flatten(hit)
            existing_facts = hit.get("texta_facts", [])

            for field in fields:
                text = flat_hit.get(field, None)
                if text and isinstance(text, str):
                    if object_type == "tagger":
                        result = tagger_object.apply_loaded_tagger(tagger, text, input_type="text", feedback=None)
                        if result:
                            tags = [result]
                        else:
                            tags = []
                    else:
                        # update text and tags with MLP
                        combined_texts, ner_tags = get_mlp(object_id, [text], lemmatize=object_args["lemmatize"], use_ner=object_args["use_ner"])
                        # retrieve tag candidates
                        tag_candidates = get_tag_candidates(object_id, [text], ignore_tags=ner_tags, n_similar_docs=object_args["n_similar_docs"],
                                                            max_candidates=object_args["n_candidate_tags"])
                        # get tags (sorted by probability in descending order)
                        tagger_group_tags = apply_tagger_group(object_id, text, tag_candidates, request=None, input_type='text', lemmatize=object_args["lemmatize"], feedback=False,
                                                               use_async=False)
                        # take only `max_tags` first tags
                        tags = ner_tags + tagger_group_tags[:max_tags]

                    new_facts = to_texta_fact(tags, field, fact_name, fact_value)
                    if new_facts:
                        existing_facts.extend(new_facts)

            if existing_facts:
                # Remove duplicates to avoid adding the same facts with repetitive use.
                existing_facts = ElasticDocument.remove_duplicate_facts(existing_facts)

            yield {
                "_index": raw_doc["_index"],
                "_id": raw_doc["_id"],
                "_type": raw_doc.get("_type", "_doc"),
                "_op_type": "update",
                "_source": {"doc": {"texta_facts": existing_facts}}
            }


@task(name="apply_tagger_to_index", base=TransactionAwareTask, queue=settings.CELERY_LONG_TERM_TASK_QUEUE)
def apply_tagger_to_index(object_id: int, indices: List[str], fields: List[str], fact_name: str, fact_value: str, query: dict, bulk_size: int, max_chunk_bytes: int,
                          es_timeout: int, object_type: str, object_args: Dict, max_tags: int = 10000):
    """Apply Tagger or TaggerGroup to index."""
    try:
        tagger = None
        if object_type == "tagger":
            tagger_object = Tagger.objects.get(pk=object_id)
            tagger = tagger_object.load_tagger(lemmatize=object_args["lemmatize"], use_logger=True)
        else:
            tagger_object = TaggerGroup.objects.get(pk=object_id)

        task_object = tagger_object.tasks.last()
        progress = ShowProgress(task_object)

        ec = ElasticCore()
        [ec.add_texta_facts_mapping(index) for index in indices]

        searcher = ElasticSearcher(
            indices=indices,
            field_data=fields + ["texta_facts"],  # Get facts to add upon existing ones.
            query=query,
            output=ElasticSearcher.OUT_RAW,
            timeout=f"{es_timeout}m",
            callback_progress=progress,
        )

        actions = update_generator(generator=searcher, ec=ec, fields=fields, fact_name=fact_name, fact_value=fact_value, max_tags=max_tags, object_id=object_id,
                                   object_type=object_type, tagger_object=tagger_object, object_args=object_args, tagger=tagger)
        for success, info in streaming_bulk(client=ec.es, actions=actions, refresh="wait_for", chunk_size=bulk_size, max_chunk_bytes=max_chunk_bytes, max_retries=3):
            if not success:
                logging.getLogger(settings.ERROR_LOGGER).exception(json.dumps(info))

        task_object.complete()
        return True

    except Exception as e:
        task_object = tagger_object.tasks.last()
        task_object.handle_failed_task(e)


@task(name="end_tagger_group", base=TransactionAwareTask, queue=settings.CELERY_SHORT_TERM_TASK_QUEUE)
def end_tagger_group(previous_result, tagger_group_id: int):
    logger = logging.getLogger(settings.INFO_LOGGER)

    tg = TaggerGroup.objects.get(pk=tagger_group_id)
    task_object = tg.tasks.last()
    task_object.complete()

    logger.info(f"[Tagger Group] Finished training for PK {tagger_group_id}!")
