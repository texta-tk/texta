import json
import logging
import uuid
from django.core import serializers
from celery.decorators import task
from elasticsearch.helpers import streaming_bulk
from toolkit.base_tasks import BaseTask
from toolkit.core.task.models import Task
from toolkit.elastic.index.models import Index
from django.contrib.auth.models import User
from toolkit.annotator.models import Annotator
from toolkit.core.project.models import Project
from texta_elastic.core import ElasticCore
from texta_elastic.searcher import ElasticSearcher, EMPTY_QUERY
from texta_elastic.document import ElasticDocument
from texta_elastic.mapping_tools import update_field_types, update_mapping, get_selected_fields
from toolkit.settings import ERROR_LOGGER, INFO_LOGGER
from toolkit.tools.show_progress import ShowProgress


def add_field_type(fields):
    field_type = []
    for field in fields:
        field_type.append({"path": field["path"], "field_type": field["type"]})
    return field_type


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


def add_doc_uuid(generator: ElasticSearcher):
    for i, scroll_batch in enumerate(generator):
        for raw_doc in scroll_batch:
            hit = raw_doc["_source"]
            existing_texta_meta = hit.get("texta_meta", {})

            if "document_uuid" not in existing_texta_meta:
                new_id = {"document_uuid": str(uuid.uuid4())}

                yield {
                    "_index": raw_doc["_index"],
                    "_id": raw_doc["_id"],
                    "_type": raw_doc.get("_type", "_doc"),
                    "_op_type": "update",
                    "_source": {"doc": {"texta_meta": new_id}}
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
        users.append(user_val["pk"])

    task_object = annotator_obj.task
    indices = json.loads(json.dumps(indices))
    users = json.loads(json.dumps(users))
    annotator_fields = json.loads(annotator_obj.fields)
    all_fields = annotator_fields
    all_fields.append("texta_meta.document_uuid")
    all_fields.append("texta_facts")
    project_obj = Project.objects.get(id=annotator_obj.project_id)
    new_field_type = get_selected_fields(indices, annotator_fields)
    field_type = add_field_type(new_field_type)
    add_facts_mapping = annotator_obj.add_facts_mapping
    scroll_size = 100

    new_indices = []
    new_annotators = []

    for user in users:
        annotating_user = User.objects.get(pk=user)
        new_annotators.append(annotating_user.pk)
        for index in indices:
            new_indices.append(f"{index}_{user}_{annotator_obj.task_id}")

    query = annotator_obj.query

    logging.getLogger(INFO_LOGGER).info(f"Starting task annotator with Task ID {annotator_obj.task_id}.")

    try:
        ec = ElasticCore()
        index_fields = ec.get_fields(indices)
        index_fields = [index_field["path"] for index_field in index_fields]

        show_progress = ShowProgress(task_object, multiplier=1)
        show_progress.update_step("scrolling data")
        show_progress.update_view(0)

        index_elastic_search = ElasticSearcher(indices=indices, field_data=index_fields, callback_progress=show_progress,
                                         query=query, output=ElasticSearcher.OUT_RAW, scroll_size=scroll_size)
        index_actions = add_doc_uuid(generator=index_elastic_search)
        for success, info in streaming_bulk(client=ec.es, actions=index_actions, refresh="wait_for", chunk_size=scroll_size, max_retries=3):
            if not success:
                logging.getLogger(ERROR_LOGGER).exception(json.dumps(info))

        for new_annotator in new_annotators:
            new_annotator_obj = Annotator.objects.create(
                description=f"{annotator_obj.description}_{new_annotator}_{annotator_obj.task_id}",
                author=annotator_obj.author,
                project=annotator_obj.project,
                total=annotator_obj.total,
                fields=json.dumps(annotator_fields),
                add_facts_mapping=add_facts_mapping,
                annotation_type=annotator_obj.annotation_type,
                binary_configuration=annotator_obj.binary_configuration,
                multilabel_configuration=annotator_obj.multilabel_configuration,
                entity_configuration=annotator_obj.entity_configuration,
            )
            new_annotator_obj.annotator_users.add(new_annotator)
            for new_index in new_indices:
                logging.getLogger(INFO_LOGGER).info(f"New Index check {new_index} for user {new_annotator}")
                logging.getLogger(INFO_LOGGER).info(f"Index object {indices}")

                for index in indices:
                    if new_index == f"{index}_{new_annotator}_{annotator_obj.task_id}":

                        elastic_search = ElasticSearcher(indices=indices, field_data=all_fields, callback_progress=show_progress, query=query, scroll_size=scroll_size)
                        elastic_doc = ElasticDocument(new_index)

                        logging.getLogger(INFO_LOGGER).info(f"Updating index schema for index {new_index}")
                        ''' the operations that don't require a mapping update have been completed '''
                        schema_input = update_field_types(indices, all_fields, field_type, flatten_doc=False)
                        updated_schema = update_mapping(schema_input, new_index, add_facts_mapping, add_texta_meta_mapping=True)

                        logging.getLogger(INFO_LOGGER).info(f"Creating new index {new_index} for user {new_annotator}")
                        # create new_index
                        create_index_res = ElasticCore().create_index(new_index, updated_schema)

                        index_model, is_created = Index.objects.get_or_create(name=new_index)
                        project_obj.indices.add(index_model)
                        index_user = index_model.name.rsplit('_', 2)[1]
                        if str(index_user) == str(new_annotator):
                            new_annotator_obj.indices.add(index_model)

                        logging.getLogger(INFO_LOGGER).info("Indexing documents.")
                        # set new_index name as mapping name
                        bulk_add_documents(elastic_search, elastic_doc, index=new_index, chunk_size=scroll_size, flatten_doc=False)

            if "texta_meta.document_uuid" in annotator_fields:
                annotator_fields.remove("texta_meta.document_uuid")
                new_annotator_obj.fields = json.dumps(annotator_fields)
            new_annotator_obj.save()
            if "texta_meta.document_uuid" not in annotator_fields:
                annotator_fields.append("texta_meta.document_uuid")
            logging.getLogger(INFO_LOGGER).info(f"Saving new annotator object ID {new_annotator_obj.id}")

            new_annotator_obj.add_annotation_mapping(new_indices)
            new_annotator_obj.add_texta_meta_mapping(new_indices)

        annotator_obj.annotator_users.clear()
        annotator_obj.save()

        # declare the job done
        task_object.complete()

    except Exception as e:
        logging.getLogger(ERROR_LOGGER).exception(e)
        task_object.add_error(str(e))
        task_object.update_status(Task.STATUS_FAILED)
        raise e

    logging.getLogger(INFO_LOGGER).info(f"Annotator with Task ID {annotator_obj.task_id} successfully completed.")
    return True
