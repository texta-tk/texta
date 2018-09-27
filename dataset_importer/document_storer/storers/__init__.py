import os, sys
file_dir = os.path.dirname(__file__)
sys.path.append(file_dir)
try:
    from elastic_storer import ElasticStorer
except:
    print('failed to import ElasticStorer from elastic_storer')