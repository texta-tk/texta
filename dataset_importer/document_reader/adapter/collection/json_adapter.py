import json


class JSONAdapter(object):

    @staticmethod
    def get_features(file_obj):
        for line in file_obj:
            yield json.loads(line)