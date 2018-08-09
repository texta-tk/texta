import os
import json
import fnmatch

META_FILE_SUFFIX = '.meta.json'


class EntityReader(object):

    @staticmethod
    def get_file_list(root_directory, extension):
        matches = []
        for directory, directory_names, file_names in os.walk(root_directory):
            for filename in fnmatch.filter(file_names, '*.{0}'.format(extension)):
                matches.append(os.path.join(directory, filename))

        return matches

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
    def count_documents(root_directory, extension):
        document_count = 0
        for directory, directory_names, file_names in os.walk(root_directory):
            document_count += len(fnmatch.filter(file_names, '*.{0}'.format(extension)))

        return document_count
