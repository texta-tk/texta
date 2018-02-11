import glob
import os
import json

META_FILE_SUFFIX = '.meta.json'


class EntityAdapter(object):

    @staticmethod
    def get_file_list(directory_path, extension):
        for file_name in glob.glob(os.path.join(directory_path, '*.' + extension)):
            yield file_name

    @staticmethod
    def get_meta_features(file_path):
        meta_file_path = file_path.rsplit('.', 1)[0] + META_FILE_SUFFIX

        if os.path.exists(meta_file_path):
            with open(meta_file_path) as meta_file:
                features = json.load(meta_file)
        else:
            features = {}

        return features

    @staticmethod
    def count_documents(directory_path, extension):
        return len(glob.glob(os.path.join(directory_path, '*.' + extension)))
