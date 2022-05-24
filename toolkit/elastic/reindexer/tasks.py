import json
import logging
from typing import List

from celery.decorators import task

from toolkit.base_tasks import BaseTask
from toolkit.core.task.models import Task
from toolkit.elastic.index.models import Index
from toolkit.elastic.reindexer.models import Reindexer
from texta_elastic.core import ElasticCore
from texta_elastic.document import ElasticDocument
from texta_elastic.mapping_tools import update_field_types, update_mapping
from texta_elastic.searcher import ElasticSearcher
from toolkit.settings import ERROR_LOGGER, INFO_LOGGER
from toolkit.tools.show_progress import ShowProgress


""" TODOs:
    unique name problem and testing it.
"""

# TODO: add this to reindex task params
FLATTEN_DOC = False


def unflatten_doc(doc):
    """ Unflatten document retrieved from ElasticSearcher.
    """
    unflattened_doc = {}
    nested_fields = [(k, v) for k, v in doc.items() if '.' in k]
    not_nested_fields = {k: v for k, v in doc.items() if '.' not in k}
    unflattened_doc.update(not_nested_fields)
    for k, v in nested_fields:
        layers = k.split('.')
        for i, layer in enumerate(layers):
            if i == 0:
                if layer not in unflattened_doc:
                    unflattened_doc[layer] = {}
                nested_branch = unflattened_doc
            elif i < len(layers) - 1:
                if layer not in nested_branch[layers[i - 1]]:
                    nested_branch[layers[i - 1]][layer] = {}
                nested_branch = nested_branch[layers[i - 1]]
            else:
                if layer not in nested_branch[layers[i - 1]]:
                    nested_branch[layers[i - 1]][layer] = v
                nested_branch = nested_branch[layers[i - 1]]
    return unflattened_doc


def apply_custom_processing(elastic_search, flatten_doc=False):
    for document in elastic_search:
        new_doc = document
        if not flatten_doc:
            new_doc = unflatten_doc(new_doc)

        yield new_doc


def apply_field_changes_generator(generator, index: str, field_data: List[dict]):
    for document in generator:
        for field in field_data:
            old_path = field["path"]
            if old_path in document:
                new_field = field["new_path_name"]
                document[new_field] = document.pop(old_path)

        yield {
            "_index": index,
            "_type": "_doc",
            "_source": document
        }


def bulk_add_documents(elastic_search: ElasticSearcher, elastic_doc: ElasticDocument, index: str, chunk_size: int, field_data: List[dict], flatten_doc=False, ):
    new_docs = apply_custom_processing(elastic_search, flatten_doc)
    actions = apply_field_changes_generator(new_docs, index, field_data)
    # No need to wait for indexing to actualize, hence refresh is False.
    elastic_doc.bulk_add_generator(actions=actions, chunk_size=chunk_size, refresh="wait_for")


@task(name="reindex_task", base=BaseTask)
def reindex_task(reindexer_task_id):
    logging.getLogger(INFO_LOGGER).info("Starting task 'reindex'.")
    try:
        reindexer_obj = Reindexer.objects.get(pk=reindexer_task_id)
        task_object = reindexer_obj.task
        indices = json.loads(reindexer_obj.indices)
        fields = json.loads(reindexer_obj.fields)
        random_size = reindexer_obj.random_size
        field_type = json.loads(reindexer_obj.field_type)
        scroll_size = reindexer_obj.scroll_size
        new_index = reindexer_obj.new_index
        query = json.loads(reindexer_obj.query)

        # if no fields, let's use all fields from all selected indices
        if not fields:
            fields = ElasticCore().get_fields(indices)
            fields = [field["path"] for field in fields]

        show_progress = ShowProgress(task_object, multiplier=1)
        show_progress.update_step("scrolling data")
        show_progress.set_progress()

        elastic_search = ElasticSearcher(indices=indices, field_data=fields, callback_progress=show_progress, query=query, scroll_size=scroll_size)
        elastic_doc = ElasticDocument(new_index)

        if random_size > 0:
            elastic_search = elastic_search.random_documents(size=random_size)

        logging.getLogger(INFO_LOGGER).info("Updating index schema.")
        ''' the operations that don't require a mapping update have been completed '''
        schema_input = update_field_types(indices, fields, field_type, flatten_doc=FLATTEN_DOC)
        updated_schema = update_mapping(schema_input, new_index, reindexer_obj.add_facts_mapping, add_texta_meta_mapping=False)

        logging.getLogger(INFO_LOGGER).info("Creating new index.")
        # create new_index
        create_index_res = ElasticCore().create_index(new_index, updated_schema)
        Index.objects.get_or_create(name=new_index)

        logging.getLogger(INFO_LOGGER).info("Indexing documents.")
        # set new_index name as mapping name, perhaps make it customizable in the future
        bulk_add_documents(elastic_search, elastic_doc, index=new_index, chunk_size=scroll_size, flatten_doc=FLATTEN_DOC, field_data=field_type)

        # declare the job done
        task_object.complete()

    except Exception as e:
        logging.getLogger(ERROR_LOGGER).exception(e)
        task_object.add_error(str(e))
        task_object.update_status(Task.STATUS_FAILED)
        raise e

    logging.getLogger(INFO_LOGGER).info("Reindexing succesfully completed.")
    return True
