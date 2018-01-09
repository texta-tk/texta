import csv
from collection_adapter import CollectionAdapter


class CSVAdapter(CollectionAdapter):

    @staticmethod
    def get_features(**kwargs):
        directory = kwargs['directory']

        for file_path in CSVAdapter.get_file_list(directory, 'csv'):
            with open(file_path) as csv_file:
                reader = csv.DictReader(csv_file)
                for row_idx, row in enumerate(reader):
                    row['_texta_id'] = '{0}_{1}'.format(file_path, row_idx)
                    yield row

    @staticmethod
    def count_total_documents(**kwargs):
        directory = kwargs['directory']

        total_documents = 0

        for file_path in CSVAdapter.get_file_list(directory, 'csv'):
            with open(file_path) as csv_file:
                reader = csv.reader(csv_file)
                total_documents += max(0, sum(1 for row in reader) - 1)  # -1 for the header

        return total_documents