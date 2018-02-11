from .settings import extractor_map
import os


class ArchiveExtractor(object):

    @staticmethod
    def extract_archive(file_path, archive_format):
        if archive_format in extractor_map:
            extractor = extractor_map[archive_format]['class']
            extractor.extract(file_path)
            os.remove(file_path)