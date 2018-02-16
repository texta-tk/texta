import tarfile
import os


class TarExtractor(object):
    """Implementation of extracting tarballs and their compressed versions.
    """

    @staticmethod
    def extract(file_path):
        """Extracts tarballs into the tarballs' directory.

        SIDE EFFECT: extracts tarball contents to the same directory where tarball is.

        :param file_path: absolute path to the tarball.
        :type file_path: string
        """
        tar_directory = os.path.dirname(file_path)

        with tarfile.open(name=file_path) as tar_file:
            tar_file.extractall(path=tar_directory)

if __name__ == '__main__':
    TarExtractor.extract('../test_target/test.tar.gz')