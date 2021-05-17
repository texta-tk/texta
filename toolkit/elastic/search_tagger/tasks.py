import json
import logging
from celery.decorators import task
from toolkit.core.task.models import Task
from toolkit.base_tasks import TransactionAwareTask
from toolkit.settings import CELERY_LONG_TERM_TASK_QUEUE, INFO_LOGGER, ERROR_LOGGER
from typing import List, Union, Dict
from toolkit.elastic.search_tagger.models import SearchQueryTagger, SearchFieldsTagger
from toolkit.tools.show_progress import ShowProgress
from toolkit.elastic.tools.core import ElasticCore
from toolkit.elastic.tools.searcher import ElasticSearcher
from toolkit.elastic.tools.document import ElasticDocument


def to_texta_facts(tagger_result: List[Dict[str, Union[str, int, bool]]], field: str, fact_name: str, fact_value: str):
    """ Format search tagger as texta facts."""
    if tagger_result["result"] == "false":
        return []

    new_fact = {
        "fact": fact_name,
        "str_val": fact_value,
        "doc_path": field,
        "spans": json.dumps([[0,0]])
    }
    return [new_fact]


def update_search_query_generator(generator: ElasticSearcher, ec: ElasticCore, fields: List[str], fact_name: str, fact_value: str, tagger_object: SearchQueryTagger):
    for i, scroll_batch in enumerate(generator):
        logging.getLogger(INFO_LOGGER).info(f"Appyling Search Query Tagger with ID {tagger_object.id}...")
        for raw_doc in scroll_batch:
            hit = raw_doc["_source"]
            flat_hit = ec.flatten(hit)
            existing_facts = hit.get("texta_facts", [])

            for field in fields:
                text = flat_hit.get(field, None)
                if text and isinstance(text, str):

                    result = {
                                'tagger_id': tagger_object.id,
                                'result': tagger_object.fact_name
                                }

                    if result["result"]:
                        if not fact_value:
                            fact_value = tagger_object.description

                    else:
                        fact_value = result["result"]

                    new_facts = to_texta_facts(result, field, fact_name, fact_value)
                    existing_facts.extend(new_facts)

            if existing_facts:
                # Remove duplicates to avoid adding the same facts with repetitive use.
                existing_facts = ElasticDocument.remove_duplicate_facts(existing_facts)

            yield {
                "_index": raw_doc["_index"],
                "_id": raw_doc["_id"],
                "_type": raw_doc.get("_type", "_doc"),
                "_op_type": "update",
                "_source": {"doc": {"texta_facts": existing_facts}},
                "retry_on_conflict": 3
            }


def update_search_fields_generator(generator: ElasticSearcher, ec: ElasticCore, fields: List[str], fact_name: str, tagger_object: SearchQueryTagger):
    for i, scroll_batch in enumerate(generator):
        logging.getLogger(INFO_LOGGER).info(f"Appyling Search Fields Tagger with ID {tagger_object.id}...")
        for raw_doc in scroll_batch:
            hit = raw_doc["_source"]
            flat_hit = ec.flatten(hit)
            existing_facts = hit.get("texta_facts", [])

            for field in fields:
                text = flat_hit.get(field, None)
                if text and isinstance(text, str):
                    if len(text) <= 100:
                        result = {
                                    'tagger_id': tagger_object.id,
                                    'result': text
                                    }
                        fact_value = result["result"]
                    else:
                        continue

                    new_facts = to_texta_facts(result, field, fact_name, fact_value)
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


@task(name="apply_search_query_tagger_on_index", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE)
def apply_search_query_tagger_on_index(object_id: int):
    search_query_tagger = SearchQueryTagger.objects.get(pk=object_id)
    task_object = search_query_tagger.task
    """Apply Search Query Tagger to index."""
    try:
        progress = ShowProgress(task_object)
        progress.update_step('scrolling search query')

        # Get the necessary fields.
        indices: List[str] = search_query_tagger.get_indices()
        fields: List[str] = json.loads(search_query_tagger.fields)
        fact_name: List[str] = search_query_tagger.fact_name
        fact_value: List[str] = search_query_tagger.fact_value

        ec = ElasticCore()
        [ec.add_texta_facts_mapping(index) for index in indices]

        print(json.loads(search_query_tagger.query))

        searcher = ElasticSearcher(
            indices=indices,
            field_data=fields + ["texta_facts"],  # Get facts to add upon existing ones.
            query=json.loads(search_query_tagger.query),
            output=ElasticSearcher.OUT_RAW,
            scroll_timeout="30m",
            callback_progress=progress,
            scroll_size=100
        )

        actions = update_search_query_generator(generator=searcher, ec=ec, fields=fields, fact_name=fact_name, fact_value=fact_value, tagger_object=search_query_tagger)
        # Send the data towards Elasticsearch
        ed = ElasticDocument("_all")
        elastic_response = ed.bulk_update(actions=actions)
        return object_id

    except Exception as e:
        logging.getLogger(ERROR_LOGGER).exception(e)
        task_object.add_error(str(e))
        task_object.update_status(Task.STATUS_FAILED)
        raise e

@task(name="apply_search_fields_tagger_on_index", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE)
def apply_search_fields_tagger_on_index(object_id: int):
    search_fields_tagger = SearchFieldsTagger.objects.get(pk=object_id)
    task_object = search_fields_tagger.task
    """Apply Search Fields Tagger to index."""
    try:
        progress = ShowProgress(task_object)
        progress.update_step('scrolling search fields')

        # Get the necessary fields.
        indices: List[str] = search_fields_tagger.get_indices()
        fields: List[str] = json.loads(search_fields_tagger.fields)
        fact_name: List[str] = search_fields_tagger.fact_name

        ec = ElasticCore()
        [ec.add_texta_facts_mapping(index) for index in indices]

        searcher = ElasticSearcher(
            indices=indices,
            field_data=fields + ["texta_facts"],  # Get facts to add upon existing ones.
            query=json.loads(search_fields_tagger.query),
            output=ElasticSearcher.OUT_RAW,
            scroll_timeout="30m",
            callback_progress=progress,
            scroll_size=100
        )

        actions = update_search_fields_generator(generator=searcher, ec=ec, fields=fields, fact_name=fact_name, tagger_object=search_fields_tagger)
        # Send the data towards Elasticsearch
        ed = ElasticDocument("_all")
        elastic_response = ed.bulk_update(actions=actions)
        return object_id

    except Exception as e:
        logging.getLogger(ERROR_LOGGER).exception(e)
        task_object.add_error(str(e))
        task_object.update_status(Task.STATUS_FAILED)
        raise e
