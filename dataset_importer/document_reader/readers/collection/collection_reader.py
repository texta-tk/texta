import glob
import os

META_FILE_SUFFIX = '.meta.json'


class CollectionReader(object):

    @staticmethod
    def get_file_list(directory_path, extension):
        for file_name in glob.glob(os.path.join(directory_path, '*.' + extension)):
            yield file_name
