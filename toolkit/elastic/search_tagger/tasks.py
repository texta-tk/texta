import json
import logging
from typing import Any, List

from celery.decorators import task
from texta_elastic.core import ElasticCore
from texta_elastic.document import ElasticDocument
from texta_elastic.searcher import ElasticSearcher

from toolkit.base_tasks import TransactionAwareTask
from toolkit.elastic.search_tagger.models import SearchFieldsTagger, SearchQueryTagger
from toolkit.settings import CELERY_LONG_TERM_TASK_QUEUE, INFO_LOGGER
from toolkit.tools.show_progress import ShowProgress


def to_texta_facts(field: str, fact_name: str, fact_value: str):
    """ Format search tagger as texta facts."""

    new_fact = {
        "fact": fact_name.strip(),
        "str_val": fact_value.strip(),
        "doc_path": field,
        "spans": json.dumps([[0, 0]]),
        "sent_index": 0
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

                    new_facts = to_texta_facts(field, fact_name, fact_value)
                    existing_facts.extend(new_facts)

            if existing_facts:
                # Remove duplicates to avoid adding the same facts with repetitive use.
                existing_facts = ElasticDocument.remove_duplicate_facts(existing_facts)

            yield {
                "_index": raw_doc["_index"],
                "_id": raw_doc["_id"],
                "_type": raw_doc.get("_type", "_doc"),
                "_op_type": "update",
                "doc": {"texta_facts": existing_facts},
                "retry_on_conflict": 3
            }


def handle_field_content(field_content: Any, breakup_character: str, use_breakup: bool, size_limit=100) -> List:
    split_texts = []
    if field_content and isinstance(field_content, str):
        # Only keep texts smaller than 100 characters.
        if use_breakup is False and len(field_content) <= size_limit:
            split_texts = [field_content]
        # Split up text by the specified character/text.
        elif use_breakup is True:
            split_texts = field_content.split(breakup_character)
            split_texts = [split_text for split_text in split_texts if len(split_text) <= size_limit]
    # Return list content as is since we're dealing with lists anyway.
    elif field_content and isinstance(field_content, list):
        split_texts = field_content

    return split_texts


def update_search_fields_generator(
        generator: ElasticSearcher,
        ec: ElasticCore, fields: List[str],
        fact_name: str,
        search_field_tagger_object: SearchFieldsTagger,
        use_breakup: bool,
        breakup_character: str
):
    for i, scroll_batch in enumerate(generator):
        logging.getLogger(INFO_LOGGER).info(f"Applying Search Fields Tagger with ID {search_field_tagger_object.id}...")
        for raw_doc in scroll_batch:
            hit = raw_doc["_source"]
            flat_hit = ec.flatten(hit)
            existing_facts = hit.get("texta_facts", [])

            for field in fields:
                field_content = flat_hit.get(field, None)
                processed_content = handle_field_content(field_content, breakup_character, use_breakup)

                for content in processed_content:
                    new_facts = to_texta_facts(field, fact_name, fact_value=content)
                    existing_facts.extend(new_facts)

            if existing_facts:
                # Remove duplicates to avoid adding the same facts with repetitive use.
                existing_facts = ElasticDocument.remove_duplicate_facts(existing_facts)

            yield {
                "_index": raw_doc["_index"],
                "_id": raw_doc["_id"],
                "_type": raw_doc.get("_type", "_doc"),
                "_op_type": "update",
                "doc": {"texta_facts": existing_facts}
            }


@task(name="start_search_query_tagger_worker", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE, bind=True)
def start_search_query_tagger_worker(self, object_id: int):
    logging.getLogger(INFO_LOGGER).info(f"Starting applying search query tagger on the index for model ID: {object_id}")
    searchquerytagger_object = SearchQueryTagger.objects.get(pk=object_id)
    task_object = searchquerytagger_object.tasks.last()
    show_progress = ShowProgress(task_object, multiplier=1)
    show_progress.update_step('running search query tagger')
    show_progress.update_view(0)
    return object_id


@task(name="apply_search_query_tagger_on_index", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE)
def apply_search_query_tagger_on_index(object_id: int):
    search_query_tagger = SearchQueryTagger.objects.get(pk=object_id)
    task_object = search_query_tagger.tasks.last()
    """Apply Search Query Tagger to index."""
    try:
        progress = ShowProgress(task_object)
        progress.update_step('scrolling search query')

        # Get the necessary fields.
        indices: List[str] = search_query_tagger.get_indices()
        fields: List[str] = json.loads(search_query_tagger.fields)
        fact_name: str = search_query_tagger.fact_name
        fact_value: str = search_query_tagger.fact_value
        scroll_timeout = search_query_tagger.es_timeout
        scroll_size = search_query_tagger.bulk_size

        ec = ElasticCore()
        [ec.add_texta_facts_mapping(index) for index in indices]

        searcher = ElasticSearcher(
            indices=indices,
            field_data=fields + ["texta_facts"],  # Get facts to add upon existing ones.
            query=json.loads(search_query_tagger.query),
            output=ElasticSearcher.OUT_RAW,
            scroll_timeout=f"{scroll_timeout}m",
            callback_progress=progress,
            scroll_size=scroll_size
        )

        actions = update_search_query_generator(generator=searcher, ec=ec, fields=fields, fact_name=fact_name, fact_value=fact_value, tagger_object=search_query_tagger)
        # Send the data towards Elasticsearch
        ed = ElasticDocument("_all")
        elastic_response = ed.bulk_update(actions=actions)
        return object_id

    except Exception as e:
        task_object.handle_failed_task(e)
        raise e


@task(name="end_search_query_tagger_task", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE, bind=True)
def end_search_query_tagger_task(self, object_id):
    logging.getLogger(INFO_LOGGER).info(f"Finished applying search query tagger on the index for model ID: {object_id}")
    searchquerytagger_object = SearchQueryTagger.objects.get(pk=object_id)
    searchquerytagger_object.tasks.last().complete()
    return True


@task(name="start_search_fields_tagger_worker", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE, bind=True)
def start_search_fields_tagger_worker(self, object_id: int):
    logging.getLogger(INFO_LOGGER).info(f"Starting applying search fields tagger on the index for model ID: {object_id}")
    searchfieldstagger_object = SearchFieldsTagger.objects.get(pk=object_id)
    show_progress = ShowProgress(searchfieldstagger_object.tasks.last(), multiplier=1)
    show_progress.update_step('running search fields tagger')
    show_progress.update_view(0)
    return object_id


@task(name="apply_search_fields_tagger_on_index", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE)
def apply_search_fields_tagger_on_index(object_id: int):
    search_fields_tagger = SearchFieldsTagger.objects.get(pk=object_id)
    task_object = search_fields_tagger.tasks.last()
    """Apply Search Fields Tagger to index."""
    try:
        progress = ShowProgress(task_object)
        progress.update_step('scrolling search fields')

        # Get the necessary fields.
        indices: List[str] = search_fields_tagger.get_indices()
        fields: List[str] = json.loads(search_fields_tagger.fields)
        fact_name: str = search_fields_tagger.fact_name
        scroll_timeout = search_fields_tagger.es_timeout
        scroll_size = search_fields_tagger.bulk_size

        use_breakup = search_fields_tagger.use_breakup
        breakup_character = search_fields_tagger.breakup_character

        ec = ElasticCore()
        [ec.add_texta_facts_mapping(index) for index in indices]

        searcher = ElasticSearcher(
            indices=indices,
            field_data=fields + ["texta_facts"],  # Get facts to add upon existing ones.
            query=json.loads(search_fields_tagger.query),
            output=ElasticSearcher.OUT_RAW,
            scroll_timeout=f"{scroll_timeout}m",
            callback_progress=progress,
            scroll_size=scroll_size
        )

        actions = update_search_fields_generator(
            generator=searcher,
            ec=ec,
            fields=fields,
            fact_name=fact_name,
            search_field_tagger_object=search_fields_tagger,
            use_breakup=use_breakup,
            breakup_character=breakup_character
        )

        # Send the data towards Elasticsearch
        ed = ElasticDocument("_all")
        elastic_response = ed.bulk_update(actions=actions)
        return object_id

    except Exception as e:
        task_object.handle_failed_task(e)
        raise e


@task(name="end_search_fields_tagger_task", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE, bind=True)
def end_search_fields_tagger_task(self, object_id):
    logging.getLogger(INFO_LOGGER).info(f"Finished applying search fields tagger on the index for model ID: {object_id}")
    searchfieldstagger_object = SearchFieldsTagger.objects.get(pk=object_id)
    searchfieldstagger_object.tasks.last().complete()
    return True
