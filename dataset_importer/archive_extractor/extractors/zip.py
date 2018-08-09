import os
import zipfile

from base_extractor import BaseExtractor

class ZipExtractor(BaseExtractor):
    """Implementation of extracting zip files.
    """

    @staticmethod
    def extract(file_path):
        """Extracts zip files into the zip files' directory.

        SIDE EFFECT: extracts zip file contents to the same directory where zip file is.

        :param file_path: absolute path to the zip file.
        :type file_path: string
        """
        zip_directory = os.path.dirname(file_path)

        with zipfile.ZipFile(file_path) as zip_file:
            zip_file.extractall(path=zip_directory)

    @staticmethod
    def detect_archives(root_directory):
        return BaseExtractor.detect_archives(root_directory=root_directory, extensions=['zip'])


if __name__ == '__main__':
    ZipExtractor.extract('../test_target/test_zip_content.zip')