import csv


class CSVAdapter(object):

    @staticmethod
    def get_features(file_obj):
        reader = csv.DictReader(file_obj)
        for row in reader:
            yield row