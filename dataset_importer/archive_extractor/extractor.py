import extractor_instance as extractor
import os


extractor_map = {
    'zip': extractor.zip.ZipExtractor,
    'tar': extractor.tar.TarExtractor,
}

class ArchiveExtractor(object):

    @staticmethod
    def extract_archive(file_path, archive_format):
        if archive_format in extractor_map:
            extractor = extractor_map[archive_format]
            extractor.extract(file_path)
            os.remove(file_path)