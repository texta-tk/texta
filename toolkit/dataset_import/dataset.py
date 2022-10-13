import logging
import os

import pandas as pd
from texta_elastic.document import ElasticDocument

from toolkit.helper_functions import chunks
from toolkit.settings import INFO_LOGGER


class Dataset:
    TYPE_CSV = '.csv'
    TYPE_XLS = '.xls'
    TYPE_XLSX = '.xlsx'
    TYPE_JSON = ['.jsonl', '.jl', '.jsonlines']


    def __init__(self, file_path, index: str, separator=',', show_progress=None, meta=None):
        """

        :param file_path: File path towards the file being imported.
        :param index: Which index to import the contents into.
        :param separator: Which separator to use when parsing csv files.
        :param show_progress: Callback class to keep track of progress.
        :param meta: Class which contains info for task ID and its description. In this case the DatasetImporter ORM object.
        """
        self.file_path = file_path
        self.separator = separator
        self.show_progress = show_progress
        self.index = index
        self.num_records = 0
        self.num_records_success = 0
        self.meta = meta
        self.logger = logging.getLogger(INFO_LOGGER)


    def _get_file_content(self):
        """Retrieves DataFrame for a collection from given path."""
        _, file_extension = os.path.splitext(self.file_path)
        file_extension = file_extension.lower()
        if file_extension == Dataset.TYPE_CSV:
            # CSV
            self.logger.info(f"Parsing CSV file content of task ID: '{self.meta.pk}' with description: '{self.meta.description}'!")
            return True, pd.read_csv(self.file_path, header=0, sep=self.separator)

        elif file_extension in (Dataset.TYPE_XLS, Dataset.TYPE_XLSX):
            # EXCEL
            self.logger.info(f"Parsing Excel file content of task ID: '{self.meta.pk}' with description: '{self.meta.description}'!")
            return True, pd.read_excel(self.file_path, header=0)

        elif file_extension in Dataset.TYPE_JSON:
            # JSON-LINES
            with open(self.file_path) as fh:
                self.logger.info(f"Parsing JSON-lines file content of task ID: '{self.meta.pk}' with description: '{self.meta.description}'!")
                return True, pd.read_json(fh, lines=True)

        # nothing parsed
        return False, None


    def import_dataset(self) -> list:
        error_container = []
        # retrieve content from file
        success, file_content = self._get_file_content()
        file_content = file_content.dropna(how="all")

        # check if file was parsed
        if not success:
            error_container.append('unknown file type')
            return error_container

        # convert content to list of records (dicts)
        self.logger.info(f"Converting parsed content into dictionary records of task ID: '{self.meta.pk}' with description: '{self.meta.description}'!")
        records = file_content.to_dict(orient='records')
        # set num_records
        self.num_records = len(records)
        # set total number of documents for progress
        if self.show_progress:
            self.show_progress.set_total(self.num_records)

        # add documents to ES
        es_doc = ElasticDocument(self.index)

        # create index
        self.logger.info(f"Creating index for fresh dataset: '{self.index}' of task ID: '{self.meta.pk}' with description: '{self.meta.description}'!")
        es_doc.core.create_index(self.index)

        # add mapping for texta facts
        self.logger.info(f"Adding texta_facts mapping to freshly created index of task ID: '{self.meta.pk}' with description: '{self.meta.description}'!")
        es_doc.core.add_texta_facts_mapping(self.index)

        # get records
        self.logger.info(f"Preparing chunks for Elasticsearch insertion of task ID: '{self.meta.pk}' with description: '{self.meta.description}'!")
        chunk_size = 500
        records = [{k: v for k, v in record.items() if pd.Series(v).notna().all()} for record in records]
        record_chunks = list(chunks(records, chunk_size))

        self.logger.info(f"Starting bulk insertion into Elasticsearch of task ID: '{self.meta.pk}' with description: '{self.meta.description}'!")

        for documents in record_chunks:
            success, errors = es_doc.bulk_add(documents, chunk_size=chunk_size, stats_only=False, raise_on_error=False)
            self.num_records_success += success

            if self.show_progress:
                self.show_progress.update(success)

            for error in list(errors):
                message = error["index"]["error"]["reason"] if isinstance(error, dict) else str(error)
                error_container.append(message)

        self.logger.info(f"Finished indexing documents into Elasticsearch of task ID: '{self.meta.pk}' with description: '{self.meta.description}'!")
        return error_container
