import logging
from typing import List
from .sumy import Sumy
from texta_elastic.searcher import ElasticSearcher
from toolkit.settings import INFO_LOGGER


def process_actions(generator: ElasticSearcher, field_data: List[str], ratio: float, algorithm: List[str], summarizer_class: Sumy, summarizer_id: int):
    counter = 0
    info_logger = logging.getLogger(INFO_LOGGER)
    info_logger.info(f"Starting the processing of indices for Summarizer worker with ID of {summarizer_id}!")
    for document_batch in generator:
        document_sources = [dict(hit["_source"]) for hit in document_batch]
        summarizer_processed = summarizer_class.run_on_index(document_sources, doc_paths=field_data, ratio=ratio, algorithm=algorithm)

        for index, summarizer_processed_document in enumerate(summarizer_processed):
            original_elastic_document = document_batch[index]

            elastic_update_body = {
                "_id": original_elastic_document["_id"],
                "_index": original_elastic_document["_index"],
                "_type": original_elastic_document.get("_type", "_doc"),
                "_op_type": "update",
                "doc": {**summarizer_processed_document}
            }

            yield elastic_update_body

            counter += 1
            progress = generator.callback_progress
            if counter % generator.scroll_size == 0:
                info_logger.info(f"Progress on applying Summarizer for worker with id: {summarizer_id} at {counter} out of {progress.n_total} documents!")
            elif counter == progress.n_total:
                info_logger.info(f"Finished applying Summarizer for worker with id: {summarizer_id} at {counter}/{progress.n_total} documents!")
