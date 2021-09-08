import json
import logging
from typing import List
from celery.decorators import task
from elasticsearch.helpers import streaming_bulk
from toolkit.elastic.tools.core import ElasticCore
from toolkit.elastic.tools.document import ElasticDocument
from toolkit.elastic.tools.searcher import ElasticSearcher
from toolkit.base_tasks import TransactionAwareTask
from toolkit.settings import CELERY_LONG_TERM_TASK_QUEUE, ERROR_LOGGER, INFO_LOGGER
from toolkit.rakun_keyword_extractor.models import RakunExtractor
from toolkit.tools.show_progress import ShowProgress
from toolkit.helper_functions import get_indices_from_object, load_stop_words
from texta_tools.embedding import FastTextEmbedding
from mrakun import RakunDetector


def update_generator(generator: ElasticSearcher, ec: ElasticCore, fields: List[str], rakun_extractor_object: RakunExtractor, fact_name: str, fact_value: str, add_spans: bool):
    for scroll_batch in generator:
        for raw_doc in scroll_batch:
            hit = raw_doc["_source"]
            flat_hit = ec.flatten(hit)
            existing_facts = hit.get("texta_facts", [])

            for field in fields:
                text = flat_hit.get(field, None)
                if text and isinstance(text, str):
                    keyword_detector = RakunDetector()
                    results = keyword_detector.find_keywords(text, input_type="text")
                    #results = rakun_extractor_object.apply([text], field_path=field, fact_name=fact_name, fact_value=fact_value, add_spans=add_spans)
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
        indices = get_indices_from_object(rakun_extractor_object)
        field_data = json.loads(rakun_extractor_object.fields)
        stop_words = load_stop_words(rakun_extractor_object.stopwords)

        # load embedding if any
        if rakun_extractor_object.fasttext_embedding:
            embedding = FastTextEmbedding()
            embedding.load_django(rakun_extractor_object.fasttext_embedding)
        else:
            embedding = None

        #actions = update_generator(generator=searcher, ec=ec, fields=fields, rakun_extractor_object=rakun_extractor_object, fact_name=fact_name, fact_value=fact_value, add_spans=add_spans)
        #for success, info in streaming_bulk(client=ec.es, actions=actions, refresh="wait_for", chunk_size=bulk_size, max_chunk_bytes=max_chunk_bytes):
        #    if not success:
        #        logging.getLogger(ERROR_LOGGER).exception(json.dumps(info))

        rakun_extractor_object.task.complete()
        return True

    except Exception as e:
        logging.getLogger(ERROR_LOGGER).exception(e)
        error_message = f"{str(e)[:100]}..."  # Take first 100 characters in case the error message is massive.
        rakun_extractor_object.task.add_error(error_message)
        rakun_extractor_object.task.update_status(task.STATUS_FAILED)
