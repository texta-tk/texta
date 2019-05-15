import os

from toolkit.settings import BASE_DIR

def get_version():
    """
    Imports version number from file system.
    :return: version as string.
    """
    try:
        with open(os.path.join(BASE_DIR, 'VERSION'), 'r') as fh:
            version = fh.read()
    except IOError:
        version = 'unknown'
    return version
