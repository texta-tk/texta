import logging
from typing import List

from celery.decorators import task
from texta_elastic.core import ElasticCore
from texta_elastic.document import ElasticDocument
from texta_elastic.searcher import ElasticSearcher

from toolkit.base_tasks import TransactionAwareTask
from toolkit.rakun_keyword_extractor.models import RakunDetectorWrapper, RakunExtractor
from toolkit.settings import CELERY_LONG_TERM_TASK_QUEUE, INFO_LOGGER
from toolkit.tools.show_progress import ShowProgress


def update_generator(keyword_detector: RakunDetectorWrapper, generator: ElasticSearcher, ec: ElasticCore, fields: List[str], rakun_extractor_object: RakunExtractor, fact_name: str, fact_value: str, add_spans: bool):
    for scroll_batch in generator:
        for raw_doc in scroll_batch:
            hit = raw_doc["_source"]
            flat_hit = ec.flatten(hit)
            existing_facts = hit.get("texta_facts", [])

            for field in fields:
                text = flat_hit.get(field, None)
                if text and isinstance(text, str):
                    results = rakun_extractor_object.get_rakun_keywords(keyword_detector=keyword_detector, texts=[text], field_path=field, fact_name=fact_name, fact_value=fact_value, add_spans=add_spans)
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


@task(name="start_rakun_task", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE, bind=True)
def start_rakun_task(self, object_id: int):
    rakun = RakunExtractor.objects.get(pk=object_id)
    task_object = rakun.tasks.last()
    show_progress = ShowProgress(task_object, multiplier=1)
    show_progress.update_step('starting rakun')
    show_progress.update_view(0)
    return object_id


@task(name="apply_rakun_extractor_to_index", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE, bind=True)
def apply_rakun_extractor_to_index(self, object_id: int, indices: List[str], fields: List[str], query: dict, es_timeout: int, bulk_size: int, fact_name: str, add_spans: bool):
    """Apply Rakun Keyword Extractor to index."""
    logging.getLogger(INFO_LOGGER).info(f"Starting task 'apply_rakun_extractor_to_index' with ID: {object_id}!")
    rakun_extractor_object = RakunExtractor.objects.get(id=object_id)
    task_object = rakun_extractor_object.tasks.last()
    try:
        progress = ShowProgress(task_object)

        # retrieve fields
        field_data = fields

        ec = ElasticCore()
        [ec.add_texta_facts_mapping(index) for index in indices]

        searcher = ElasticSearcher(
            indices=indices,
            field_data=field_data + ["texta_facts"],  # Get facts to add upon existing ones.
            query=query,
            timeout=f"{es_timeout}m",
            output=ElasticSearcher.OUT_RAW,
            callback_progress=progress,
            scroll_size=bulk_size
        )
        keyword_detector = rakun_extractor_object.load_rakun_keyword_detector()
        actions = update_generator(keyword_detector=keyword_detector, generator=searcher, ec=ec, fields=field_data, rakun_extractor_object=rakun_extractor_object, fact_name=fact_name, fact_value="", add_spans=add_spans)

        # Send the data towards Elasticsearch
        ed = ElasticDocument("_all")
        elastic_response = ed.bulk_update(actions=actions)

        task_object.complete()
        return True

    except Exception as e:
        task_object.handle_failed_task(e)
        raise e
