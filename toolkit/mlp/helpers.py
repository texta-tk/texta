import logging
from typing import List
from celery.task.control import inspect
from pelecanus import PelicanJson

from texta_mlp.document import Document
from texta_mlp.mlp import MLP

from texta_elastic.document import ElasticDocument
from texta_elastic.searcher import ElasticSearcher
from toolkit.settings import INFO_LOGGER, NAN_LANGUAGE_TOKEN_KEY


def parse_doc_texts(doc_path: str, document: dict) -> list:
    """
    Function for parsing text values from a nested dictionary given a field path.
    :param doc_path: Dot separated path of fields to the value we wish to parse.
    :param document: Document to be worked on.
    :return: List of text fields that will be processed by MLP.
    """
    wrapper = PelicanJson(document)
    doc_path_as_list = doc_path.split(".")
    content = wrapper.safe_get_nested_value(doc_path_as_list, default=[])
    if content and isinstance(content, str):
        return [content]
    # Check that content is non-empty list and there are only stings in the list.
    elif content and isinstance(content, list) and all([isinstance(list_content, str) for list_content in content]):
        return content
    # In case the field path is faulty and it gives you a dictionary instead.
    elif isinstance(content, dict):
        return []
    else:
        return []


def process_mlp_actions(generator: ElasticSearcher, analyzers: List[str], field_data: List[str], mlp_class: MLP, mlp_id: int):
    """
    ElasticSearcher returns a list of 100 RAW elastic documents.
    Since MLP needs a raw document to process, we need to memorize the index of the document in question
    so that we could later fetch it's metadata for the Bulk generator.
    """
    counter = 0
    info_logger = logging.getLogger(INFO_LOGGER)

    info_logger.info(f"Starting the processing of indices for MLP worker with ID of {mlp_id}!")
    for document_batch in generator:
        document_sources = [dict(hit["_source"]) for hit in document_batch]
        mlp_processed = mlp_class.process_docs(document_sources, analyzers=analyzers, doc_paths=field_data)

        for index, mlp_processed_document in enumerate(mlp_processed):
            original_elastic_document = document_batch[index]

            # Make sure that existing facts in the document and new ones don't overlap.
            original_facts = original_elastic_document["_source"].get("texta_facts", [])
            new_facts = mlp_processed_document.get("texta_facts", [])
            total_facts = [fact for fact in original_facts + new_facts if fact]
            unique_facts = ElasticDocument.remove_duplicate_facts(total_facts)

            elastic_update_body = {
                "_id": original_elastic_document["_id"],
                "_index": original_elastic_document["_index"],
                "_type": original_elastic_document.get("_type", "_doc"),
                "_op_type": "update",
                "doc": {**mlp_processed_document, **{"texta_facts": unique_facts}}
            }

            yield elastic_update_body

            counter += 1
            progress = generator.callback_progress
            if counter % generator.scroll_size == 0:
                info_logger.info(f"Progress on applying MLP for worker with id: {mlp_id} at {counter} out of {progress.n_total} documents!")
            elif counter == progress.n_total:
                info_logger.info(f"Finished applying MLP for worker with id: {mlp_id} at {counter}/{progress.n_total} documents!")


def process_lang_actions(generator: ElasticSearcher, field: str, worker_id: int, mlp_class: MLP):
    counter = 0
    info_logger = logging.getLogger(INFO_LOGGER)

    info_logger.info(f"Applying language detection to the worker with an ID of {worker_id}!")
    for document_batch in generator:
        for item in document_batch:
            # This will be a list of texts.
            source = item["_source"]
            texts = parse_doc_texts(field, source)
            texts = texts if texts else [""]
            for text in texts:
                # This can be either a str or None
                lang = mlp_class.detect_language(text)
                lang = lang if lang else NAN_LANGUAGE_TOKEN_KEY
                mlp_path = f"{field}_mlp.language.detected"
                source = Document.edit_doc(source, mlp_path, lang)

                elastic_update_body = {
                    "_id": item["_id"],
                    "_index": item["_index"],
                    "_type": item.get("_type", "_doc"),
                    "_op_type": "update",
                    "retry_on_conflict": 3,
                    "doc": {**source}
                }

                yield elastic_update_body

            counter += 1
            progress = generator.callback_progress
            if counter % generator.scroll_size == 0:
                info_logger.info(f"Progress on applying language detection for worker with id: {worker_id} at {counter} out of {progress.n_total} documents!")
            elif counter == progress.n_total:
                info_logger.info(f"Finished applying language detection for worker with id: {worker_id} at {counter}/{progress.n_total} documents!")


def check_celery_tasks(QUEUE_NAME):
    """
    Checks for scheduled tasks in queue.
    """
    inspector = inspect([QUEUE_NAME])
    scheduled_tasks = inspector.scheduled()
    if not scheduled_tasks:
        return True
    else:
        return False
