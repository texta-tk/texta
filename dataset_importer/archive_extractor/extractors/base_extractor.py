import fnmatch
import os


class BaseExtractor(object):

    @staticmethod
    def detect_archives(root_directory, extensions=[]):
        matches = []
        for directory, directory_names, file_names in os.walk(root_directory):
            for extension in extensions:
                for filename in fnmatch.filter(file_names, '*.{0}'.format(extension)):
                    matches.append(os.path.join(directory, filename))

        return matches
