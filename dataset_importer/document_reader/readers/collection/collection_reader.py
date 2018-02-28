import glob
import os
import fnmatch

META_FILE_SUFFIX = '.meta.json'


class CollectionReader(object):

    @staticmethod
    def get_file_list(root_directory, extension):
        matches = []
        for directory, directory_names, file_names in os.walk(root_directory):
            for filename in fnmatch.filter(file_names, '*.{0}'.format(extension)):
                matches.append(os.path.join(directory, filename))

        return matches
