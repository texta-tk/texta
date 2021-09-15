import json
import logging
from typing import List
from celery.decorators import task
from elasticsearch.helpers import streaming_bulk
from toolkit.elastic.tools.core import ElasticCore
from toolkit.elastic.tools.document import ElasticDocument
from toolkit.elastic.tools.searcher import ElasticSearcher
from toolkit.base_tasks import TransactionAwareTask
from toolkit.settings import CELERY_LONG_TERM_TASK_QUEUE, ERROR_LOGGER, INFO_LOGGER, FACEBOOK_MODEL_SUFFIX
from toolkit.rakun_keyword_extractor.models import RakunExtractor
from toolkit.tools.show_progress import ShowProgress
from toolkit.helper_functions import load_stop_words


def update_generator(generator: ElasticSearcher, ec: ElasticCore, fields: List[str], rakun_extractor_object: RakunExtractor, fact_name: str, fact_value: str, add_spans: bool, **hyperparamaters: dict):
    for scroll_batch in generator:
        for raw_doc in scroll_batch:
            hit = raw_doc["_source"]
            flat_hit = ec.flatten(hit)
            existing_facts = hit.get("texta_facts", [])

            for field in fields:
                text = flat_hit.get(field, None)
                if text and isinstance(text, str):
                    results = rakun_extractor_object.get_rakun_keywords([text], field_path=fields, fact_name=fact_name, fact_value=fact_value, add_spans=add_spans, hyperparameters=hyperparamaters)
                    existing_facts.extend(results)

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

@task(name="start_rakun_task", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE)
def start_rakun_task(object_id: int):
    rakun = RakunExtractor.objects.get(pk=object_id)
    task_object = rakun.task
    show_progress = ShowProgress(task_object, multiplier=1)
    show_progress.update_step('starting rakun')
    show_progress.update_view(0)
    return object_id

@task(name="apply_rakun_extractor_to_index", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE)
def apply_rakun_extractor_to_index(object_id: int):
    """Apply Rakun Keyword Extractor to index."""
    try:
        logging.getLogger(INFO_LOGGER).info(f"Starting task 'apply_rakun_extractor_to_index' with ID: {object_id}!")
        rakun_extractor_object = RakunExtractor.objects.get(id=object_id)

        progress = ShowProgress(rakun_extractor_object.task)

        # retrieve indices & field data
        indices = rakun_extractor_object.get_indices()
        field_data = json.loads(rakun_extractor_object.fields)
        stop_words = load_stop_words(rakun_extractor_object.stopwords)
        if int(rakun_extractor_object.min_tokens) == int(rakun_extractor_object.max_tokens):
            num_tokens = [int(rakun_extractor_object.min_tokens)]
        else:
            num_tokens = [int(rakun_extractor_object.min_tokens), int(rakun_extractor_object.max_tokens)]

        # load embedding if any
        if rakun_extractor_object.fasttext_embedding:
            embedding_model_path = str(rakun_extractor_object.fasttext_embedding.embedding_model)
            gensim_embedding_model_path = embedding_model_path + "_" + FACEBOOK_MODEL_SUFFIX
        else:
            gensim_embedding_model_path = None


        ec = ElasticCore()
        [ec.add_texta_facts_mapping(index) for index in indices]

        searcher = ElasticSearcher(
            indices=indices,
            field_data=field_data + ["texta_facts"],  # Get facts to add upon existing ones.
            query=rakun_extractor_object.query,
            timeout="10m",
            output=ElasticSearcher.OUT_RAW,
            callback_progress=progress,
            scroll_size=100
        )

        HYPERPARAMETERS = {"distance_threshold": rakun_extractor_object.distance_threshold,
                           "distance_method": rakun_extractor_object.distance_method,
                           "pretrained_embedding_path": gensim_embedding_model_path,
                           "num_keywords": rakun_extractor_object.num_keywords,
                           "pair_diff_length": rakun_extractor_object.pair_diff_length,
                           "stopwords": stop_words,
                           "bigram_count_threshold": rakun_extractor_object.bigram_count_threshold,
                           "num_tokens": num_tokens,
                           "max_similar": rakun_extractor_object.max_similar,
                           "max_occurrence": rakun_extractor_object.max_occurrence,
                           "lemmatizer": None}

        actions = update_generator(generator=searcher, ec=ec, fields=field_data, rakun_extractor_object=rakun_extractor_object, fact_name="rakun", fact_value="", add_spans=True, hyperparameters=HYPERPARAMETERS)
        for success, info in streaming_bulk(client=ec.es, actions=actions, refresh="wait_for", chunk_size=100, max_chunk_bytes=104857600):
            if not success:
                logging.getLogger(ERROR_LOGGER).exception(json.dumps(info))

        rakun_extractor_object.task.complete()
        return True

    except Exception as e:
        logging.getLogger(ERROR_LOGGER).exception(e)
        error_message = f"{str(e)[:100]}..."  # Take first 100 characters in case the error message is massive.
        rakun_extractor_object.task.add_error(error_message)
        rakun_extractor_object.task.update_status(task.STATUS_FAILED)
