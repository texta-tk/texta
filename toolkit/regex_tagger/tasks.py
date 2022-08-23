import json
import logging
from typing import List, Optional, Union

from celery.decorators import task
from elasticsearch.helpers import streaming_bulk
from texta_elastic.core import ElasticCore
from texta_elastic.document import ElasticDocument
from texta_elastic.searcher import ElasticSearcher

from toolkit.base_tasks import TransactionAwareTask
from toolkit.regex_tagger.choices import PRIORITY_CHOICES
from toolkit.regex_tagger.models import RegexTagger, RegexTaggerGroup, load_matcher
from toolkit.settings import CELERY_LONG_TERM_TASK_QUEUE, ERROR_LOGGER
from toolkit.tools.show_progress import ShowProgress


def load_taggers(tagger_object: RegexTaggerGroup):
    taggers = []
    for regex_tagger in tagger_object.regex_taggers.all():
        matcher = load_matcher(regex_tagger)

        taggers.append({
            "tagger_id": regex_tagger.id,
            "description": regex_tagger.description,
            "matcher": matcher
        })

    return taggers


def process_texta_facts(facts: List[str], priority: Optional[str] = None):
    if priority == PRIORITY_CHOICES[0][0]:  # First choice
        pass
    elif priority == PRIORITY_CHOICES[1][0]:  # Last choice
        pass
    elif priority is None:
        return facts


def update_generator(generator: ElasticSearcher, ec: ElasticCore, fields: List[str], tagger_object: Union[RegexTagger, RegexTaggerGroup], fact_name: str, fact_value: str, add_spans: bool):
    for scroll_batch in generator:
        for raw_doc in scroll_batch:
            hit = raw_doc["_source"]
            flat_hit = ec.flatten(hit)
            existing_facts = hit.get("texta_facts", [])

            for field in fields:
                text = flat_hit.get(field, None)
                if text and isinstance(text, str):
                    results = tagger_object.apply([text], field_path=field, fact_name=fact_name, fact_value=fact_value, add_spans=add_spans)
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


@task(name="apply_regex_tagger_to_index", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE)
def apply_regex_tagger(object_id: int, object_type: str, indices: List[str], fields: List[str], query: dict, es_timeout: int = 10, bulk_size: int = 100, max_chunk_bytes: int = 104857600, fact_name: str = "", fact_value: str = "", add_spans: bool = True):
    """Apply RegexTagger or RegexTaggerGroup to index."""
    try:
        if object_type == "regex_tagger_group":
            tagger_object = RegexTaggerGroup.objects.get(pk=object_id)
        else:
            tagger_object = RegexTagger.objects.get(pk=object_id)

        task_object = tagger_object.tasks.last()
        progress = ShowProgress(task_object)

        ec = ElasticCore()
        [ec.add_texta_facts_mapping(index) for index in indices]

        searcher = ElasticSearcher(
            indices=indices,
            field_data=fields + ["texta_facts"],  # Get facts to add upon existing ones.
            query=query,
            timeout=f"{es_timeout}m",
            output=ElasticSearcher.OUT_RAW,
            callback_progress=progress,
            scroll_size=bulk_size
        )

        actions = update_generator(generator=searcher, ec=ec, fields=fields, tagger_object=tagger_object, fact_name=fact_name, fact_value=fact_value, add_spans=add_spans)
        for success, info in streaming_bulk(client=ec.es, actions=actions, refresh="wait_for", chunk_size=bulk_size, max_chunk_bytes=max_chunk_bytes):
            if not success:
                logging.getLogger(ERROR_LOGGER).exception(json.dumps(info))

        task_object.complete()
        return True

    except Exception as e:
        task_object.handle_failed_task(e)
        raise e
