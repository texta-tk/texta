import json
import logging
from collections import defaultdict

from celery.decorators import task

from toolkit.base_tasks import BaseTask
from toolkit.elastic.core import ElasticCore
from toolkit.elastic.document import ElasticDocument
from toolkit.elastic.mapping_generator import SchemaGenerator
from toolkit.elastic.models import Reindexer
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.tools.show_progress import ShowProgress
from toolkit.settings import ERROR_LOGGER, INFO_LOGGER


""" TODOs:
    unique name problem and testing it.
"""

# TODO: add this to reindex task params
FLATTEN_DOC = False


def get_selected_fields(indices, fields):
    # get all fields in given indices
    all_fields = ElasticCore().get_fields(indices)
    # filter out selected fields
    selected_fields = [field for field in all_fields if field["path"] in fields]
    return selected_fields


def add_nested(fields):
    for field in fields:
        if '.' in field['path']:
            field['type'] = 'nested'
    return fields


def reformat_for_schema_generator(fields, flatten_doc=False):
    if not flatten_doc:
        fields = add_nested(fields)
    formatted_fields = defaultdict(list)
    for field in fields:
        if field['path'] == 'texta_facts':
            formatted_fields['texta_facts'].append('texta_facts')
        else:
            formatted_fields[field['type']].append(field['path'])
    return dict(formatted_fields)


def update_field_types(indices, fields, field_type, flatten_doc=False):
    ''' if fieldtype, for field named fieldtype change its type'''

    # returns fields edited by serializer input
    my_fields = get_selected_fields(indices, fields)
    my_field_data = [field["path"] for field in my_fields]

    for item in field_type:
        if item['path'] in my_field_data:
            field_to_edit = item['path']
            new_type = item['field_type']

            for field in my_fields:
                if field['path'] == field_to_edit:
                    field['type'] = new_type
                    # TODO must work, also when only name is changed
                    if 'new_path_name' in item.keys():
                        new_path_name = item['new_path_name']
                        field['path'] = new_path_name
    updated_field_types = reformat_for_schema_generator(my_fields, flatten_doc)
    return updated_field_types


def update_mapping(schema_input, new_index, add_facts_mapping):
    mod_schema = SchemaGenerator().generate_schema(schema_input, add_facts_mapping)
    return {'mappings': {new_index: mod_schema}}


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


def apply_elastic_search(elastic_search, flatten_doc=False):
    for document in elastic_search:
        new_doc = document
        if not flatten_doc:
            new_doc = unflatten_doc(new_doc)

        yield new_doc


def elastic_bulk_generator(generator, index: str):
    for document in generator:
        yield {
            "_index": index,
            "_type": index,
            "_source": document
        }


def bulk_add_documents(elastic_search: ElasticSearcher, elastic_doc: ElasticDocument, index: str, chunk_size: int, flatten_doc=False):
    new_docs = apply_elastic_search(elastic_search, flatten_doc)
    actions = elastic_bulk_generator(new_docs, index)
    # No need to wait for indexing to actualize, hence refresh is False.
    elastic_doc.bulk_add_raw(actions=actions, chunk_size=chunk_size, refresh=False)


@task(name="reindex_task", base=BaseTask)
def reindex_task(reindexer_task_id):
    reindexer_obj = Reindexer.objects.get(pk=reindexer_task_id)
    task_object = reindexer_obj.task
    indices = json.loads(reindexer_obj.indices)
    fields = json.loads(reindexer_obj.fields)
    random_size = reindexer_obj.random_size
    field_type = json.loads(reindexer_obj.field_type)
    scroll_size = reindexer_obj.scroll_size
    new_index = reindexer_obj.new_index
    query = reindexer_obj.query

    logging.getLogger(INFO_LOGGER).info("Starting task 'reindex'.")

    try:
        ''' for empty field post, use all posted indices fields '''
        if not fields:
            fields = ElasticCore().get_fields(indices)
            fields = [field["path"] for field in fields]

        show_progress = ShowProgress(task_object, multiplier=1)
        show_progress.update_step("scrolling data")
        show_progress.update_view(0)

        elastic_search = ElasticSearcher(indices=indices, field_data=fields, callback_progress=show_progress, query=query, scroll_size=scroll_size)
        elastic_doc = ElasticDocument(new_index)

        if random_size > 0:
            elastic_search = ElasticSearcher(indices=indices, field_data=fields, query=query, scroll_size=scroll_size).random_documents(size=random_size)

        logging.getLogger(INFO_LOGGER).info("Updating index schema.")
        ''' the operations that don't require a mapping update have been completed '''
        schema_input = update_field_types(indices, fields, field_type, flatten_doc=FLATTEN_DOC)
        updated_schema = update_mapping(schema_input, new_index, reindexer_obj.add_facts_mapping)

        logging.getLogger(INFO_LOGGER).info("Creating new index.")
        # create new_index
        create_index_res = ElasticCore().create_index(new_index, updated_schema)

        logging.getLogger(INFO_LOGGER).info("Indexing documents.")
        # set new_index name as mapping name, perhaps make it customizable in the future
        bulk_add_documents(elastic_search, elastic_doc, index=new_index, chunk_size=scroll_size, flatten_doc=FLATTEN_DOC)

        # declare the job done
        task_object.complete()

    except Exception as e:
        logging.getLogger(ERROR_LOGGER).exception(e)
        task_object.add_error(str(e))
        task_object.update_status(Task.STATUS_FAILED)
        raise e

    logging.getLogger(INFO_LOGGER).info("Reindexing succesfully completed.")
    return True
