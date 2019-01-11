import csv
from collection_reader import CollectionReader
import sys

from dataset_importer.utils import HandleDatasetImportException

maxInt = sys.maxsize
decrement = True

while decrement:
    # decrease the maxInt value by factor 10
    # as long as the OverflowError occurs.

    decrement = False
    try:
        csv.field_size_limit(maxInt)
    except OverflowError:
        maxInt = int(maxInt/10)
        decrement = True


class CSVReader(CollectionReader):

    @staticmethod
    def get_features(**kwargs):
        directory = kwargs['directory']

        for file_path in CSVReader.get_file_list(directory, 'csv'):
            try:
                with open(file_path, encoding='UTF-8') as csv_file:
                    reader = csv.DictReader(csv_file)
                    for row_idx, row in enumerate(reader):
                        row['_texta_id'] = '{0}_{1}'.format(file_path, row_idx)
                        yield row

            except Exception as e:
                HandleDatasetImportException(kwargs, e, file_path=file_path)

    @staticmethod
    def count_total_documents(**kwargs):
        directory = kwargs['directory']

        total_documents = 0

        for file_path in CSVReader.get_file_list(directory, 'csv'):
            with open(file_path, encoding='UTF-8') as csv_file:
                reader = csv.reader(csv_file)
                total_documents += max(0, sum(1 for row in reader) - 1)  # -1 for the header

        return total_documents
