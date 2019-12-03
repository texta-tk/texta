import pandas as pd
import os

from toolkit.elastic.document import ElasticDocument

class Dataset:
    TYPE_CSV = '.csv'
    TYPE_XLS = '.xls'
    TYPE_XLSX = '.xlsx'
    TYPE_JSON = '.json'

    def __init__(self, file_path, index, separator=',', show_progress=None):
        self.file_path = file_path
        self.separator = separator
        self.show_progress = show_progress
        self.index = index
        self.num_records = 0
        self.num_records_success = 0

    def _get_file_content(self):
        '''Retrieves DataFrame for a collection from given path.'''
        _, file_extension = os.path.splitext(self.file_path)
        file_extension = file_extension.lower()
        if file_extension == Dataset.TYPE_CSV:
            # CSV
            return True, pd.read_csv(self.file_path, header=0, sep=self.separator)
        elif file_extension in (Dataset.TYPE_XLS, Dataset.TYPE_XLSX):
            # EXCEL
            return True, pd.read_excel(self.file_path, header=0, sep=self.separator)
        elif file_extension == Dataset.TYPE_JSON:
            # JSON-LINES
            with open(self.file_path) as fh:
                json_content = fh.read()
            return True, pd.read_json(json_content, lines=True)
        # nothing parsed
        return False, None
    
    def import_dataset(self):
        errors = []
        # retrieve content from file
        success, file_content = self._get_file_content()
        # check if file was parsed
        if not success:
            errors.append('unknown file type')
            return errors
        # convert content to list of records (dicts)
        records = file_content.to_dict(orient='records')
        # set num_records
        self.num_records = len(records)
        # set total number of documents for progress
        if self.show_progress:
            self.show_progress.set_total(self.num_records)
        # add documents to ES
        es_doc = ElasticDocument(self.index)
        for record in records:
            # remove nan values
            record = {k: v for k, v in record.items() if pd.Series(v).notna().all()}
            # add to Elastic
            try:
                es_doc.add(record)
                self.num_records_success += 1
            except Exception as e:
                errors.append(e)
            # update progress
            if self.show_progress:
                self.show_progress.update(1)
        # return errors
        return errors
