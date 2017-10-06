import tarfile
import os


class TarExtractor(object):

    @staticmethod
    def extract(file_path):
        tar_directory = os.path.dirname(file_path)

        with tarfile.open(name=file_path) as tar_file:
            tar_file.extractall(path=tar_directory)

if __name__ == '__main__':
    TarExtractor.extract('../test_target/test.tar.gz')