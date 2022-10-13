import json
import logging
import uuid
from typing import List

import texta_mlp.settings
from celery.decorators import task
from django.contrib.auth.models import User
from elasticsearch.helpers import streaming_bulk
from texta_elastic.core import ElasticCore
from texta_elastic.document import ESDocObject, ElasticDocument
from texta_elastic.mapping_tools import get_selected_fields, update_field_types, update_mapping
from texta_elastic.searcher import ElasticSearcher

from toolkit.annotator.models import Annotator, AnnotatorGroup
from toolkit.base_tasks import BaseTask
from toolkit.core.project.models import Project
from toolkit.elastic.index.models import Index
from toolkit.settings import ERROR_LOGGER, INFO_LOGGER
from toolkit.tools.show_progress import ShowProgress


def add_field_type(fields):
    field_type = []
    for field in fields:
        field_type.append({"path": field["path"], "field_type": field["type"]})
    return field_type


def unflatten_doc(doc):
    """ Unflatten document retrieved from ElasticSearcher."""
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
    """
    Add unique document ID's so that annotations across multiple sub-indices could be mapped together in the end. Refer to https://git.texta.ee/texta/texta-rest/-/issues/589
    :param generator: Source of elasticsearch documents, can be any iterator.
    """
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


def __add_meta_to_original_index(indices: List[str], index_fields: List[str], show_progress: ShowProgress, query: dict, scroll_size: int, elastic_wrapper: ElasticCore):
    index_elastic_search = ElasticSearcher(
        indices=indices,
        field_data=index_fields,
        callback_progress=show_progress,
        query=query,
        output=ElasticSearcher.OUT_RAW,
        scroll_size=scroll_size
    )
    index_actions = add_doc_uuid(generator=index_elastic_search)
    for success, info in streaming_bulk(client=elastic_wrapper.es, actions=index_actions, refresh="wait_for", chunk_size=scroll_size, max_retries=3):
        if not success:
            logging.getLogger(ERROR_LOGGER).exception(json.dumps(info))


@task(name="add_entity_task", base=BaseTask, bind=True)
def add_entity_task(self, pk: int, document_id: str, texta_facts: List[dict], index: str, user_pk: int):
    annotator_obj = Annotator.objects.get(pk=pk)
    user_obj = User.objects.get(pk=user_pk)
    ed = ESDocObject(document_id=document_id, index=index)
    filtered_facts = ed.filter_facts(fact_name=annotator_obj.entity_configuration.fact_name, doc_path=json.loads(annotator_obj.fields)[0])
    new_facts = filtered_facts + texta_facts
    if new_facts:
        for fact in new_facts:
            spans = []
            for span in json.loads(fact["spans"]):
                first, last = span
                spans.append([first, last])

            if fact["fact"] == annotator_obj.entity_configuration.fact_name:
                ed.add_fact(source=fact.get("source", "annotator"), fact_value=fact["str_val"], fact_name=fact["fact"],
                            doc_path=fact["doc_path"], spans=json.dumps(spans), sent_index=fact.get("sent_index", 0),
                            author=user_obj.username)

                annotator_obj.generate_record(document_id, index=index, user_pk=user_obj.pk, fact=fact, do_annotate=True)

        ed.add_annotated(annotator_obj, user_obj)

        ed.update()
    else:
        # In case the users marks the document as 'done' but it has no Facts to add.
        ed.add_annotated(annotator_obj, user_obj)
        ed.update()
        annotator_obj.generate_record(document_id, index=index, user_pk=user_obj.pk, do_annotate=True)


@task(name="annotator_task", base=BaseTask, bind=True)
def annotator_task(self, annotator_task_id):
    annotator_obj = Annotator.objects.get(pk=annotator_task_id)
    annotator_group_children = []

    indices = annotator_obj.get_indices()
    users = [user.pk for user in annotator_obj.annotator_users.all()]

    task_object = annotator_obj.tasks.last()
    annotator_fields = json.loads(annotator_obj.fields)
    all_fields = annotator_fields
    all_fields.append("texta_meta.document_uuid")

    if annotator_obj.annotation_type == 'entity':
        all_fields.append("texta_facts")
        all_fields.append(texta_mlp.settings.META_KEY)  # Include MLP Meta key here so it would be pulled from Elasticsearch.

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
            new_indices.append(f"{index}_{user}_{annotator_obj.pk}")

    query = annotator_obj.query

    logging.getLogger(INFO_LOGGER).info(f"Starting task annotator with Task ID {annotator_obj.pk}.")

    try:
        ec = ElasticCore()
        index_fields = ec.get_fields(indices)
        index_fields = [index_field["path"] for index_field in index_fields]

        # ElasticSearcher seems to be broken when handling scrolls with only the main field in its field_data instead of all of them in dot notation.
        # Hence this ugly hack is needed if I want to include the MLP meta field inside the output.
        for annotator_field in json.loads(annotator_obj.fields):
            for index_field in index_fields:
                stripped_mlp_field = annotator_field.split("_mlp.")[0] if "_mlp." in annotator_field else annotator_field
                if texta_mlp.settings.META_KEY in index_field and stripped_mlp_field in index_field:
                    all_fields.append(index_field)

        show_progress = ShowProgress(task_object, multiplier=1)
        show_progress.update_step("scrolling data")
        show_progress.update_view(0)

        __add_meta_to_original_index(indices, index_fields, show_progress, query, scroll_size, ec)

        for new_annotator in new_annotators:
            new_annotator_obj = Annotator.objects.create(
                annotator_uid=f"{annotator_obj.description}_{new_annotator}_{annotator_obj.pk}",
                description=f"{annotator_obj.description}",
                author=annotator_obj.author,
                project=annotator_obj.project,
                total=annotator_obj.total,
                fields=annotator_obj.fields,
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
                    if new_index == f"{index}_{new_annotator}_{annotator_obj.pk}":

                        elastic_search = ElasticSearcher(indices=indices, field_data=all_fields, callback_progress=show_progress, query=query, scroll_size=scroll_size)
                        elastic_doc = ElasticDocument(new_index)

                        logging.getLogger(INFO_LOGGER).info(f"Updating index schema for index {new_index}")
                        ''' the operations that don't require a mapping update have been completed '''
                        schema_input = update_field_types(indices, all_fields, field_type, flatten_doc=False)
                        updated_schema = update_mapping(schema_input, new_index, add_facts_mapping, add_texta_meta_mapping=True)

                        logging.getLogger(INFO_LOGGER).info(f"Creating new index {new_index} for user {new_annotator}")
                        # create new_index
                        create_index_res = ElasticCore().create_index(new_index, updated_schema)

                        index_model, is_created = Index.objects.get_or_create(name=new_index, defaults={"added_by": annotator_obj.author.username})
                        project_obj.indices.add(index_model)
                        index_user = index_model.name.rsplit('_', 2)[1]
                        if str(index_user) == str(new_annotator):
                            new_annotator_obj.indices.add(index_model)

                        logging.getLogger(INFO_LOGGER).info("Indexing documents.")
                        # set new_index name as mapping name
                        bulk_add_documents(elastic_search, elastic_doc, index=new_index, chunk_size=scroll_size, flatten_doc=False)

            new_annotator_obj.save()
            annotator_group_children.append(new_annotator_obj.id)
            logging.getLogger(INFO_LOGGER).info(f"Saving new annotator object ID {new_annotator_obj.id}")

        new_annotator_obj.add_annotation_mapping(new_indices)
        new_annotator_obj.add_texta_meta_mapping(new_indices)

        annotator_obj.annotator_users.clear()
        annotator_obj.save()

        annotator_group, is_created = AnnotatorGroup.objects.get_or_create(project=annotator_obj.project, parent=annotator_obj)
        annotator_group.children.add(*annotator_group_children)

        # declare the job done
        task_object.complete()

    except Exception as e:
        task_object.handle_failed_task(e)
        raise e

    logging.getLogger(INFO_LOGGER).info(f"Annotator with Task ID {annotator_obj.pk} successfully completed.")
    return True
