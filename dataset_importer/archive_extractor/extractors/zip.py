import os
import zipfile


class ZipExtractor(object):
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

if __name__ == '__main__':
    ZipExtractor.extract('../test_target/test_zip_content.zip')