import logging
from typing import List

from texta_mlp.mlp import MLP

from toolkit.elastic.tools.document import ElasticDocument
from toolkit.elastic.tools.searcher import ElasticSearcher
from toolkit.settings import INFO_LOGGER


def process_actions(generator: ElasticSearcher, analyzers: List[str], field_data: List[str], mlp_class: MLP, mlp_id: int):
    # ElasticSearcher returns a list of 100 RAW elastic documents.
    # Since MLP needs a raw document to process, we need to memorize the index
    # of the document in question so that we could later fetch it's metadata for the Bulk generator.
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
