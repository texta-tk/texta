import json
import logging
from django.core import serializers
from celery.decorators import task
from toolkit.base_tasks import BaseTask
from toolkit.core.task.models import Task
from toolkit.elastic.index.models import Index
from toolkit.annotator.models import Annotator
from toolkit.core.project.models import Project
from texta_elastic.core import ElasticCore
from texta_elastic.searcher import ElasticSearcher, EMPTY_QUERY
from texta_elastic.document import ElasticDocument
from texta_elastic.mapping_tools import update_field_types, update_mapping
from toolkit.settings import ERROR_LOGGER, INFO_LOGGER
from toolkit.tools.show_progress import ShowProgress


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


def annotator_bulk_generator(generator, index: str):
    for document in generator:
        yield {
            "_index": index,
            "_type": "_doc",
            "_source": document
        }


def bulk_add_documents(elastic_search: ElasticSearcher, elastic_doc: ElasticDocument, index: str, chunk_size: int, flatten_doc=False):
    new_docs = apply_elastic_search(elastic_search, flatten_doc)
    actions = annotator_bulk_generator(new_docs, index)
    # No need to wait for indexing to actualize, hence refresh is False.
    elastic_doc.bulk_add_generator(actions=actions, chunk_size=chunk_size, refresh="wait_for")



@task(name="annotator_task", base=BaseTask, bind=True)
def annotator_task(self, annotator_task_id):
    annotator_obj = Annotator.objects.get(pk=annotator_task_id)
    indices_obj = json.loads(serializers.serialize("json", annotator_obj.indices.all()))
    users_obj = json.loads(serializers.serialize("json", annotator_obj.annotator_users.all()))
    indices = []
    users = []
    for val in indices_obj:
        indices.append(val["fields"]["name"])
    for user_val in users_obj:
        users.append(user_val["fields"]["username"])
    task_object = annotator_obj.task
    print("annotator task_id", annotator_task_id)
    print("annotator obj", json.loads(json.dumps(indices)))
    print("anontator task", annotator_obj.task)
    print("annotator fields", annotator_obj.fields)
    indices = json.loads(json.dumps(indices))
    users = json.loads(json.dumps(users))
    fields = annotator_obj.fields
    project_obj = Project.objects.get(id=annotator_obj.project_id)
    print("project_id", annotator_obj.project_id)
    #fields = ""
    random_size = 10
    field_type = ""
    scroll_size = 100
    #new_index = f"annotator_new_{annotator_task_id}"
    print("users", users)
    #print("new_index", new_index)
    new_indices = []
    for user in users:
        for index in indices:
            new_indices.append(f"{user}_{index}")
    print("new_indices", new_indices)
    query = EMPTY_QUERY

    logging.getLogger(INFO_LOGGER).info("Starting task 'annotator'.")

    try:
        ''' for empty field post, use all posted indices fields '''
        if not fields:
            fields = ElasticCore().get_fields(indices)
            fields = [field["path"] for field in fields]

        show_progress = ShowProgress(task_object, multiplier=1)
        show_progress.update_step("scrolling data")
        show_progress.update_view(0)

        for new_index in new_indices:
            elastic_search = ElasticSearcher(indices=indices, field_data=fields, callback_progress=show_progress, query=query, scroll_size=scroll_size)
            elastic_doc = ElasticDocument(new_index)

            if random_size > 0:
                elastic_search = ElasticSearcher(indices=indices, field_data=fields, query=query, scroll_size=scroll_size).random_documents(size=random_size)

            logging.getLogger(INFO_LOGGER).info("Updating index schema.")
            ''' the operations that don't require a mapping update have been completed '''
            schema_input = update_field_types(indices, fields, field_type, flatten_doc=False)
            updated_schema = update_mapping(schema_input, new_index, False)

            logging.getLogger(INFO_LOGGER).info("Creating new index.")
            # create new_index
            create_index_res = ElasticCore().create_index(new_index, updated_schema)
            index_model, is_created = Index.objects.get_or_create(name=new_index)
            project_obj.indices.add(index_model)
            annotator_obj.indices.add(index_model)

            logging.getLogger(INFO_LOGGER).info("Indexing documents.")
            # set new_index name as mapping name, perhaps make it customizable in the future
            bulk_add_documents(elastic_search, elastic_doc, index=new_index, chunk_size=scroll_size, flatten_doc=False)

        # declare the job done
        task_object.complete()

    except Exception as e:
        logging.getLogger(ERROR_LOGGER).exception(e)
        task_object.add_error(str(e))
        task_object.update_status(Task.STATUS_FAILED)
        raise e

    logging.getLogger(INFO_LOGGER).info("Annotator succesfully completed.")
    return True