import logging
from typing import List, Optional

from celery.decorators import task
from elasticsearch.helpers import bulk

from toolkit.base_tasks import TransactionAwareTask
from toolkit.elastic.core import ElasticCore
from toolkit.elastic.document import ElasticDocument
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.regex_tagger.models import RegexTaggerGroup, load_matcher
from toolkit.regex_tagger.serializers import PRIORITY_CHOICES
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


def update_generator(generator: ElasticSearcher, fields: List[str], group_tagger_id: int):
    tagger = RegexTaggerGroup.objects.get(pk=group_tagger_id)

    for scroll_batch in generator:
        for raw_doc in scroll_batch:
            hit = raw_doc["_source"]
            existing_facts = hit.get("texta_facts", [])

            for field in fields:
                text = hit.get(field, None)
                if text and isinstance(text, str):
                    results = tagger.apply([text], field_path=field)
                    existing_facts.extend(results)

            if existing_facts:
                # Remove duplicates to avoid adding the same facts with repetitive use.
                hit["texta_facts"] = ElasticDocument.remove_duplicate_facts(existing_facts)

            yield {
                "_index": raw_doc["_index"],
                "_type": raw_doc["_type"],
                "_id": raw_doc["_id"],
                "_op_type": "update",
                "_source": {'doc': hit},
            }


@task(name="apply_regex_tagger", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE)
def apply_regex_tagger(tagger_group_id: int, indices: List[str], fields: List[str], query: dict):
    try:
        regex_tagger_group = RegexTaggerGroup.objects.get(pk=tagger_group_id)
        progress = ShowProgress(regex_tagger_group.task)

        ec = ElasticCore()
        [ec.add_texta_facts_mapping(index) for index in indices]

        searcher = ElasticSearcher(
            indices=indices,
            field_data=fields + ["texta_facts"],  # Get facts to add upon existing ones.
            query=query,
            output=ElasticSearcher.OUT_RAW,
            callback_progress=progress
        )

        actions = update_generator(generator=searcher, fields=fields, group_tagger_id=regex_tagger_group.pk)
        bulk(client=ec.es, actions=actions, refresh="wait_for")
        regex_tagger_group.task.complete()
        return True

    except Exception as e:
        logging.getLogger(ERROR_LOGGER).exception(e)
        regex_tagger_group.task.add_error(str(e))
