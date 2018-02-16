import os
import zipfile


class ZipExtractor(object):

    @staticmethod
    def extract(file_path):
        zip_directory = os.path.dirname(file_path)

        with zipfile.ZipFile(file_path) as zip_file:
            zip_file.extractall(path=zip_directory)

if __name__ == '__main__':
    ZipExtractor.extract('../test_target/test_zip_content.zip')