import os, sys
file_dir = os.path.dirname(__file__)
sys.path.append(file_dir)

try:
    import elastic_reader as elastic
except:
    print('failed to import elastic_reader as elastic')

try:
    import mongodb_reader as mongodb
except:
    print('failed to import mongodb_reader as mongodb')

try:
    import postgres_reader as postgres
except:
    print('failed to import postgres_reader as postgres')

try:
    import sqlite_reader as sqlite
except:
    print('failed to import sqlite_reader as sqlite')