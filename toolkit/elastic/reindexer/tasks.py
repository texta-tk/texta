import json
import logging
from typing import List

from celery.decorators import task
from texta_elastic.core import ElasticCore
from texta_elastic.document import ElasticDocument
from texta_elastic.mapping_tools import update_field_types, update_mapping
from texta_elastic.searcher import ElasticSearcher

from toolkit.base_tasks import BaseTask
from toolkit.elastic.index.models import Index
from toolkit.elastic.reindexer.models import Reindexer
from toolkit.settings import INFO_LOGGER
from toolkit.tools.show_progress import ShowProgress


""" TODOs:
    unique name problem and testing it.
"""

# TODO: add this to reindex task params
FLATTEN_DOC = False


def unflatten_doc(doc: dict):
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


def apply_custom_processing(elastic_search: ElasticSearcher, flatten_doc=False):
    for document in elastic_search:
        new_doc = document
        if not flatten_doc:
            new_doc = unflatten_doc(new_doc)

        yield new_doc


def apply_field_changes_generator(generator, index: str, field_data: List[dict]):
    all_field_names = [field["path"] for field in field_data]
    for document in generator:
        for field in field_data:
            old_path = field["path"]
            if old_path in document:
                new_field = field["new_path_name"]
                document[new_field] = document.pop(old_path)

        # Remove parts of mlp meta that are not relevant to the selected fields.
        mlp_meta = document.get("_mlp_meta", {})
        mlp_meta = {k: v for k, v in mlp_meta.items() if k in all_field_names}
        if mlp_meta:
            document["_mlp_meta"] = mlp_meta

        yield {
            "_index": index,
            "_type": "_doc",
            "_source": document
        }


def bulk_add_documents(elastic_search: ElasticSearcher, elastic_doc: ElasticDocument, index: str, chunk_size: int, field_data: List[dict], flatten_doc=False, refresh="wait_for"):
    new_docs = apply_custom_processing(elastic_search, flatten_doc)
    actions = apply_field_changes_generator(new_docs, index, field_data)
    # No need to wait for indexing to actualize, hence refresh is False.
    elastic_doc.bulk_add_generator(actions=actions, chunk_size=chunk_size, refresh=refresh)


@task(name="reindex_task", base=BaseTask)
def reindex_task(reindexer_task_id: int):
    logging.getLogger(INFO_LOGGER).info(f"Starting task 'reindex' with ID {reindexer_task_id}.")
    try:
        reindexer_obj = Reindexer.objects.get(pk=reindexer_task_id)
        task_object = reindexer_obj.tasks.last()
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
        show_progress.update_view(0)

        elastic_search = ElasticSearcher(indices=indices, field_data=fields + ["_mlp_meta"], callback_progress=show_progress, query=query, scroll_size=scroll_size)
        task_object.set_total(elastic_search.count())
        elastic_doc = ElasticDocument(new_index)

        if random_size > 0:
            elastic_search = elastic_search.random_documents(size=random_size)

        logging.getLogger(INFO_LOGGER).info(f"Updating index schema for index '{new_index}'.")
        # the operations that don't require a mapping update have been completed
        schema_input = update_field_types(indices, fields, field_type, flatten_doc=FLATTEN_DOC)
        updated_schema = update_mapping(schema_input, new_index, reindexer_obj.add_facts_mapping, add_texta_meta_mapping=False)

        logging.getLogger(INFO_LOGGER).info(f"Creating new index: '{new_index}'.")
        # create new_index
        create_index_res = ElasticCore().create_index(new_index, updated_schema)
        index, is_created = Index.objects.get_or_create(name=new_index, added_by=reindexer_obj.author.username)

        logging.getLogger(INFO_LOGGER).info(f"Indexing documents into index '{new_index}'.")
        # set new_index name as mapping name, perhaps make it customizable in the future
        bulk_add_documents(elastic_search, elastic_doc, index=new_index, chunk_size=scroll_size, flatten_doc=FLATTEN_DOC, field_data=field_type)

        reindexer_obj.project.indices.add(index)

        # declare the job done
        task_object.complete()

        logging.getLogger(INFO_LOGGER).info(f"Reindexing into index '{new_index}' succesfully completed.")
        return True


    except Exception as e:
        task_object.handle_failed_task(e)
        raise e
