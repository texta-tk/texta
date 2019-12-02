import pandas as pd
import os

from toolkit.elastic.document import ElasticDocument

class Dataset:
    TYPE_CSV = '.csv'
    TYPE_XLS = '.xls'
    TYPE_XLSX = '.xlsx'
    TYPE_JSON = '.json'

    def __init__(self, file_path, index, separator=','):
        self.file_path = file_path
        self.separator = separator
        self.index = index

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
        # retrieve content from file
        success, file_content = self._get_file_content()
        # check if file was parsed
        if not success:
            return {'error': 'unknown file type'}
        # convert content to list of records (dicts)
        records = file_content.to_dict(orient='records')
        # add documents to ES
        es_doc = ElasticDocument(self.index)
        for record in records:
            # remove nan values
            record = {k: v for k, v in record.items() if pd.Series(v).notna().all()}
            # add to Elastic

            
            es_doc.add(record)
        # return no errors
        return None