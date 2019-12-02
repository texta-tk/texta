import pandas as pd

from toolkit.elastic.document import ElasticDocument

class Dataset:
    TYPE_CSV = 'csv'
    TYPE_XLS = 'xls'
    TYPE_XLSX = 'xlsx'
    TYPE_JSON = 'json'

    def __init__(self):
        pass
    
    def import_dataset(self, dataset_import_object):
        file_path = dataset_import_object.file.name
        separator = ';'

        if file_path.endswith(Dataset.TYPE_CSV):
            file_content = pd.read_csv(file_path, header=0, sep=separator)
        elif file_path.endswith(Dataset.TYPE_XLS) or file_path.endswith(Dataset.TYPE_XLSX):
            file_content = pd.read_excel(file_path, header=0, sep=separator)
        elif file_path.endswith(Dataset.TYPE_JSON):
            with open(file_path) as fh:
                json_content = fh.read()
            file_content = pd.read_json(json_content, lines=True)
        
        es_doc = ElasticDocument(dataset_import_object.index)

        docs = file_content.to_dict(orient='records')

        #es_doc.bulk_add