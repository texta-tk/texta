"""extractors package contains specific archive extractor implementations.

List here the new archive extractors.
"""
import os, sys
file_dir = os.path.dirname(__file__)
sys.path.append(file_dir)
try:
    import tar
except:
    print('failed to import tar')

try:
    import zip
except:
    print('failed to import zip')
