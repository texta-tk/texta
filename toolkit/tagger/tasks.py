import json
import logging
import os
import pathlib
import re
import secrets
from time import sleep
from elasticsearch.helpers import streaming_bulk
from celery.decorators import task
from texta_tagger.tagger import Tagger as TextTagger
from texta_tools.embedding import W2VEmbedding
from django.db import transaction
from celery import group
from celery import chord
from celery.result import allow_join_result
from toolkit.base_tasks import BaseTask, TransactionAwareTask
from toolkit.core.task.models import Task
from toolkit.elastic.data_sample import DataSample
from toolkit.elastic.feedback import Feedback
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.elastic.core import ElasticCore
from toolkit.elastic.document import ElasticDocument
from toolkit.elastic.models import Index
from toolkit.elastic.query import Query
from toolkit.helper_functions import get_indices_from_object
from toolkit.settings import CELERY_LONG_TERM_TASK_QUEUE, CELERY_MLP_TASK_QUEUE, CELERY_SHORT_TERM_TASK_QUEUE, INFO_LOGGER, MEDIA_URL, ERROR_LOGGER
from toolkit.tagger.models import Tagger, TaggerGroup
from toolkit.tools.lemmatizer import CeleryLemmatizer, ElasticLemmatizer
from toolkit.tools.plots import create_tagger_plot
from toolkit.tools.show_progress import ShowProgress
from toolkit.mlp.tasks import apply_mlp_on_list
from toolkit.helper_functions import add_finite_url_to_feedback


from typing import List, Union, Dict

def create_tagger_batch(tagger_group_id, taggers_to_create):
    """Creates Tagger objects from list of tagger data and saves into tagger group object."""
    # retrieve Tagger Group object
    tagger_group_object = TaggerGroup.objects.get(pk=tagger_group_id)
    # iterate through batch
    logging.getLogger(INFO_LOGGER).info(f"Creating {len(taggers_to_create)} taggers for TaggerGroup ID: {tagger_group_id}!")
    for tagger_data in taggers_to_create:
        indices = [index["name"] for index in tagger_data["indices"]]
        indices = tagger_group_object.project.get_available_or_all_project_indices(indices)
        tagger_data.pop("indices")

        created_tagger = Tagger.objects.create(
            **tagger_data,
            author=tagger_group_object.author,
            project=tagger_group_object.project
        )

        for index in Index.objects.filter(name__in=indices, is_open=True):
            created_tagger.indices.add(index)

        # add and save
        tagger_group_object.taggers.add(created_tagger)
        tagger_group_object.save()
        # train
        created_tagger.train()


@task(name="create_tagger_objects", base=BaseTask, queue=CELERY_LONG_TERM_TASK_QUEUE)
def create_tagger_objects(tagger_group_id, tagger_serializer, tags, tag_queries, batch_size=100):
    """Task for creating Tagger objects inside Tagger Group to prevent database timeouts."""
    # create tagger objects
    logging.getLogger(INFO_LOGGER).info(f"Starting task 'create_tagger_objects' for TaggerGroup with ID: {tagger_group_id}!")

    taggers_to_create = []
    for i, tag in enumerate(tags):
        tagger_data = tagger_serializer.copy()
        tagger_data.update({"query": json.dumps(tag_queries[i])})
        tagger_data.update({"description": tag})
        tagger_data.update({"fields": json.dumps(tagger_data["fields"])})
        taggers_to_create.append(tagger_data)
        # if batch size reached, save result
        if len(taggers_to_create) >= batch_size:
            create_tagger_batch(tagger_group_id, taggers_to_create)
            taggers_to_create = []
    # if any taggers remaining
    if taggers_to_create:
        # create tagger objects of remaining items
        create_tagger_batch(tagger_group_id, taggers_to_create)

    logging.getLogger(INFO_LOGGER).info(f"Completed task 'create_tagger_objects' for TaggerGroup with ID: {tagger_group_id}!")
    return True


@task(name="start_tagger_task", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE)
def start_tagger_task(tagger_id: int):
    tagger = Tagger.objects.get(pk=tagger_id)
    task_object = tagger.task
    show_progress = ShowProgress(task_object, multiplier=1)
    show_progress.update_step('starting tagging')
    show_progress.update_view(0)
    return tagger_id


@task(name="train_tagger_task", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE)
def train_tagger_task(tagger_id: int):
    logging.getLogger(INFO_LOGGER).info(f"Starting task 'train_tagger' for tagger with ID: {tagger_id}!")
    tagger_object = Tagger.objects.get(id=tagger_id)
    task_object = tagger_object.task
    try:
        # create progress object
        show_progress = ShowProgress(task_object, multiplier=1)
        show_progress.update_step('scrolling positives')
        show_progress.update_view(0)

        # retrieve indices & field data
        indices = get_indices_from_object(tagger_object)
        field_data = json.loads(tagger_object.fields)
        # split stop words by space or newline and remove empties
        stop_words = re.split(" |\n|\r\n", tagger_object.stop_words)
        stop_words = [stop_word for stop_word in stop_words if stop_word]

        # get scoring function
        if tagger_object.scoring_function != "default":
            scoring_function = tagger_object.scoring_function
        else:
            scoring_function = None

        logging.getLogger(INFO_LOGGER).info(f"Using scoring function: {scoring_function}.")

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
            snowball_language=tagger_object.snowball_language
        )
        # update status to training
        show_progress.update_step("training")
        show_progress.update_view(0)
        # train model
        tagger = TextTagger(
            embedding=embedding,
            custom_stop_words=stop_words,
            classifier=tagger_object.classifier,
            vectorizer=tagger_object.vectorizer)
        tagger.train(
            data_sample.data,
            field_list=field_data,
            scoring = scoring_function
        )

        # save tagger to disk
        tagger_full_path, relative_tagger_path = tagger_object.generate_name("tagger")
        tagger.save(tagger_full_path)
        task_object.save()

        # Save the image before its path.
        image_name = f'{secrets.token_hex(15)}.png'
        tagger_object.plot.save(image_name, create_tagger_plot(tagger.report.to_dict()), save=False)
        image_path = pathlib.Path(MEDIA_URL) / image_name

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
            "plot": str(image_path)
        }

    except Exception as e:
        logging.getLogger(ERROR_LOGGER).exception(e)
        task_object.add_error(str(e))
        task_object.update_status(Task.STATUS_FAILED)
        raise e


@task(name="save_tagger_results", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE)
def save_tagger_results(result_data: dict):
    try:
        tagger_id = result_data['id']
        logging.getLogger(INFO_LOGGER).info(f"Starting task results for tagger with ID: {tagger_id}!")
        tagger_object = Tagger.objects.get(pk=tagger_id)
        task_object = tagger_object.task
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
        tagger_object.save()
        task_object.complete()
    except Exception as e:
        logging.getLogger(ERROR_LOGGER).exception(e)
        task_object.add_error(str(e))
        task_object.update_status(Task.STATUS_FAILED)
        raise e


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
        logging.getLogger(INFO_LOGGER).info(f"[Get MLP] Applying lemmatization and NER...")
        with allow_join_result():
            mlp = apply_mlp_on_list.apply_async(kwargs={"texts": [text], "analyzers": ["all"]}, queue=CELERY_MLP_TASK_QUEUE).get()
            mlp_result = mlp[0]
            logging.getLogger(INFO_LOGGER).info(f"[Get MLP] Finished applying MLP.")

    # lemmatize
    if lemmatize and mlp_result:
        text = mlp_result["text"]["lemmas"]
        lemmas_exists = True if text.strip() else False
        logging.getLogger(INFO_LOGGER).info(f"[Get MLP] Lemmatization result exists: {lemmas_exists}")

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
        logging.getLogger(INFO_LOGGER).info(f"[Get MLP] Detected {len(tags)} with NER.")

    return text, tags


def get_tag_candidates(tagger_group_id: int, text: str, ignore_tags: List[str] = [], n_similar_docs: int = 10, max_candidates: int = 10):
    """
    Finds frequent tags from documents similar to input document.
    Returns empty list if hybrid option false.
    """
    hybrid_tagger_object = TaggerGroup.objects.get(pk=tagger_group_id)
    field_paths = json.loads(hybrid_tagger_object.taggers.first().fields)
    indices = hybrid_tagger_object.project.get_indices()
    logging.getLogger(INFO_LOGGER).info(f"[Get Tag Candidates] Selecting from following indices: {indices}.")
    ignore_tags = {tag["tag"]: True for tag in ignore_tags}
    # create query
    query = Query()
    query.add_mlt(field_paths, text)
    # create Searcher object for MLT
    es_s = ElasticSearcher(indices=indices, query=query.query)
    logging.getLogger(INFO_LOGGER).info(f"[Get Tag Candidates] Trying to retrieve {n_similar_docs} documents from Elastic...")
    docs = es_s.search(size=n_similar_docs)
    logging.getLogger(INFO_LOGGER).info(f"[Get Tag Candidates] Successfully retrieved {len(docs)} documents from Elastic.")
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
    logging.getLogger(INFO_LOGGER).info(f"[Get Tag Candidates] Retrieved {len(tag_candidates)} tag candidates.")
    return tag_candidates


def load_tagger(tagger_id: int, lemmatize: bool = False, use_logger: bool = True) -> TextTagger:
    """Loading tagger model from disc."""
    if use_logger:
        logging.getLogger(INFO_LOGGER).info(f"Loading tagger with ID: {tagger_id} with params (lemmatize: {lemmatize})")
    # get tagger object
    tagger_object = Tagger.objects.get(pk=tagger_id)
    # get lemmatizer/stemmer
    if tagger_object.snowball_language:
        lemmatizer = ElasticLemmatizer(language=tagger_object.snowball_language)
    elif lemmatize:
        lemmatizer = CeleryLemmatizer()
    else:
        lemmatizer = None
    # create text processor object for tagger
    stop_words = tagger_object.stop_words.split(' ')
    # load embedding
    if tagger_object.embedding:
        embedding = W2VEmbedding()
        embedding.load_django(tagger_object.embedding)
    else:
        embedding = False
    # load tagger
    tagger = TextTagger(embedding=embedding, mlp=lemmatizer, custom_stop_words=stop_words)
    tagger_loaded = tagger.load_django(tagger_object)
    # check if tagger gets loaded
    if not tagger_loaded:
        return None
    return tagger


def apply_loaded_tagger(tagger_object: Tagger, tagger: TextTagger, content: Union [str, Dict[str, str]], input_type: str = "text", feedback: bool = False, use_logger: bool = True):
    """Applying loaded tagger."""
    # check input type
    if input_type == 'doc':
        if use_logger:
            logging.getLogger(INFO_LOGGER).info(f"Tagging document with content: {content}!")
        tagger_result = tagger.tag_doc(content)
    else:
        if use_logger:
            logging.getLogger(INFO_LOGGER).info(f"Tagging text with content: {content}!")
        tagger_result = tagger.tag_text(content)

    # Result is false if binary tagger's prediction is false, but true otherwise
    # (for multiclass, the result is always true as one of the classes is always predicted)
    result = False if tagger_result["prediction"] == "false" else True

    # Use tagger description as tag for binary taggers and tagger prediction as tag for multiclass taggers
    tag = tagger.description if tagger_result["prediction"] in {"true", "false"} else tagger_result["prediction"]

    if use_logger:
        logging.getLogger(INFO_LOGGER).info(f"Tagger description: {tagger_object.description}")
        logging.getLogger(INFO_LOGGER).info(f"Tagger result: {tagger_result['prediction']}")

    tagger_id = tagger_object.pk
    # create output dict
    prediction = {
        'tag': tag,
        'probability': tagger_result['probability'],
        'tagger_id': tagger_id,
        'result': result
    }
    # add feedback if asked
    if feedback:
        logging.getLogger(INFO_LOGGER).info(f"Adding feedback for Tagger id: {tagger_object.pk}")
        project_pk = tagger_object.project.pk
        feedback_object = Feedback(project_pk, model_object=tagger_object)
        processed_text = tagger.text_processor.process(content)[0]
        feedback_id = feedback_object.store(processed_text, prediction)
        feedback_url = f'/projects/{project_pk}/taggers/{tagger_object.pk}/feedback/'
        prediction['feedback'] = {'id': feedback_id, 'url': feedback_url}

    if use_logger:
        logging.getLogger(INFO_LOGGER).info(f"Completed task 'apply_tagger' for tagger with ID: {tagger_id}!")
    return prediction


@task(name="apply_tagger", base=BaseTask)
def apply_tagger(tagger_id: int, content: Union[str, Dict[str, str]], input_type='text', lemmatize=False, feedback=None, use_logger=True):
    """Task for applying tagger to text. Wraps functions load_tagger and apply_loaded_tagger."""
    if use_logger:
        logging.getLogger(INFO_LOGGER).info(f"Starting task 'apply_tagger' for tagger with ID: {tagger_id} with params (input_type : {input_type}, lemmatize: {lemmatize}, feedback: {feedback})!")

    tagger_object = Tagger.objects.get(pk=tagger_id)

    # Load tagger model from the disc
    tagger = load_tagger(tagger_id=tagger_id, lemmatize=lemmatize, use_logger=use_logger)

    # Use the loaded model for predicting
    prediction = apply_loaded_tagger(tagger_object=tagger_object, tagger=tagger, content=content, input_type=input_type, feedback=feedback, use_logger=use_logger)

    return prediction


def apply_tagger_group(tagger_group_id: int, content: Union[str, Dict[str, str]], tag_candidates: List[str], request, input_type: str = 'text', lemmatize: bool = False, feedback: bool = False, use_async: bool = True):
    # get tagger group object
    logging.getLogger(INFO_LOGGER).info(f"[Apply Tagger Group] Starting apply_tagger_group...")
    tagger_group_object = TaggerGroup.objects.get(pk=tagger_group_id)
    # get tagger objects
    candidates_str = "|".join(tag_candidates)
    tagger_objects = tagger_group_object.taggers.filter(description__iregex=f"^({candidates_str})$")
    # filter out completed
    tagger_objects = [tagger for tagger in tagger_objects if tagger.task.status == tagger.task.STATUS_COMPLETED]
    logging.getLogger(INFO_LOGGER).info(f"[Apply Tagger Group] Loaded {len(tagger_objects)} tagger objects.")
    # predict tags
    if use_async:
        group_task = group(apply_tagger.s(tagger.pk, content, input_type=input_type, lemmatize=lemmatize, feedback=feedback, use_logger=False) for tagger in tagger_objects)
        group_results = group_task.apply_async(queue=CELERY_SHORT_TERM_TASK_QUEUE)
        result_tags = group_results.get()

        # alternative approach for linear application (but slower!)
        #while not group_results.ready():
        #    sleep(0.000001)
        #if group_results.ready():
        #    result_tags = [t[1]["result"] for t in group_results.iter_native()]

        logging.getLogger(INFO_LOGGER).info(f"[Apply Tagger Group] Group task applied.")

    else:
        result_tags = []
        for tagger in tagger_objects:
            result = apply_tagger(tagger.pk, content, input_type=input_type, lemmatize=lemmatize, feedback=feedback)
            result_tags.append(result)

    # retrieve results & remove non-hits
    tags = [tag for tag in result_tags if tag]
    logging.getLogger(INFO_LOGGER).info(f"[Apply Tagger Group] Retrieved results for {len(tags)} taggers.")
    # remove non-hits
    tags = [tag for tag in tags if tag['result']]
    logging.getLogger(INFO_LOGGER).info(f"[Apply Tagger Group] Retrieved {len(tags)} positive tags.")
    # if feedback was enabled, add urls
    if feedback:
        tags = [add_finite_url_to_feedback(tag, request) for tag in tags]
    # sort by probability and return
    return sorted(tags, key=lambda k: k['probability'], reverse=True)


def to_texta_fact(tagger_result: List[Dict[str, Union[str, int, bool]]], field: str, fact_name: str, fact_value: str):
    new_facts = []
    for result in tagger_result:
        if result["result"]:
            str_val = fact_value if fact_value else result["tag"]
            new_fact = {
                "fact": fact_name,
                "str_val": str_val,
                "doc_path": field,
                "spans": json.dumps([[0,0]])
            }
            new_facts.append(new_fact)
    return new_facts


def update_generator(generator: ElasticSearcher, ec: ElasticCore, fields: List[str], fact_name: str, fact_value: str, object_id: int, object_type: str, object: Tagger, object_args: Dict, tagger: TextTagger = None):
    for i, scroll_batch in enumerate(generator):
        logging.getLogger(INFO_LOGGER).info(f"Appyling {object_type} with ID {object_id} to batch {i+1}...")
        for raw_doc in scroll_batch:
            hit = raw_doc["_source"]
            flat_hit = ec.flatten(hit)
            existing_facts = hit.get("texta_facts", [])

            for field in fields:
                text = flat_hit.get(field, None)
                if text and isinstance(text, str):
                    if object_type == "tagger":
                        result = apply_loaded_tagger(object, tagger,  text, input_type="text", feedback=None, use_logger = False)
                        if result:
                            result = [result]
                        else:
                            result = []
                    else:
                        # update text and tags with MLP
                        combined_texts, tags = get_mlp(object_id, [text], lemmatize=object_args["lemmatize"], use_ner=object_args["use_ner"])
                        # retrieve tag candidates
                        tag_candidates = get_tag_candidates(object_id, [text], ignore_tags=tags, n_similar_docs=object_args["n_similar_docs"], max_candidates=object_args["n_candidate_tags"])
                        # get tags
                        tags += apply_tagger_group(object_id, text, tag_candidates, request=None, input_type='text', lemmatize=object_args["lemmatize"], feedback=False, use_async=False)
                        result = tags

                    new_facts = to_texta_fact(result, field, fact_name, fact_value)
                    if new_facts:
                        existing_facts.extend(new_facts)

            if existing_facts:
                # Remove duplicates to avoid adding the same facts with repetitive use.
                existing_facts = ElasticDocument.remove_duplicate_facts(existing_facts)

            hit["texta_facts"] = existing_facts

            yield {
                "_index": raw_doc["_index"],
                "_id": raw_doc["_id"],
                "_type": raw_doc.get("_type", "_doc"),
                "_op_type": "update",
                "_source": {'doc': hit},
            }


@task(name="apply_tagger_to_index", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE)
def apply_tagger_to_index(object_id: int, indices: List[str], fields: List[str], fact_name: str, fact_value: str, query: dict, bulk_size: int, max_chunk_bytes: int, es_timeout: int, object_type: str, object_args: Dict):
    """Apply Tagger or TaggerGroup to index."""
    try:
        tagger = None
        if object_type == "tagger":
            object = Tagger.objects.get(pk=object_id)
            tagger = load_tagger(object.id, lemmatize=object_args["lemmatize"], use_logger=True)
        else:
            object = TaggerGroup.objects.get(pk=object_id)

        progress = ShowProgress(object.task)

        ec = ElasticCore()
        [ec.add_texta_facts_mapping(index) for index in indices]

        searcher = ElasticSearcher(
            indices = indices,
            field_data = fields + ["texta_facts"],  # Get facts to add upon existing ones.
            query = query,
            output = ElasticSearcher.OUT_RAW,
            timeout = f"{es_timeout}m",
            callback_progress=progress,
        )

        actions = update_generator(generator=searcher, ec=ec, fields=fields, fact_name=fact_name, fact_value=fact_value, object_id=object_id, object_type=object_type, object=object, object_args=object_args, tagger=tagger)
        for success, info in streaming_bulk(client=ec.es, actions=actions, refresh="wait_for", chunk_size=bulk_size, max_chunk_bytes=max_chunk_bytes, max_retries=3):
            if not success:
                logging.getLogger(ERROR_LOGGER).exception(json.dumps(info))

        object.task.complete()
        return True

    except Exception as e:
        logging.getLogger(ERROR_LOGGER).exception(e)
        error_message = f"{str(e)[:100]}..."  # Take first 100 characters in case the error message is massive.
        object.task.add_error(error_message)
