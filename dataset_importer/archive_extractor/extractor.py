from .settings import extractor_map
import os


class ArchiveExtractor(object):
    """A static archive extractor adapter that dispatches the extraction request to appropriate archive extractor implementation.
    """

    @staticmethod
    def extract_archive(file_path, archive_format):
        """Dispatches archive extraction request to the appropriate archive extractor implementation, if available.

        SIDE EFFECT: Removes the origial archive file.

        :param file_path: absolute path to the archive file which we want to extract
        :param archive_format: archive extractor implementations' key as listed in .settings.py:extractor_map
        :type file_path: string
        :type archive_format: string
        """
        if archive_format in extractor_map:
            extractor = extractor_map[archive_format]['class']
            extractor.extract(file_path)
            os.remove(file_path)