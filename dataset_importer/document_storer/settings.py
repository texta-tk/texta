import os, sys
file_dir = os.path.dirname(__file__)
sys.path.append(file_dir)
import storers


def log_storer_status(code, status):
    # only print if status disabled
    if status == 'disabled':
        print('[Dataset Importer] {code} storer {status}.'.format(**{'code': code, 'status': status}))


storer_map = {}

try:
    storer_map['elastic'] = {
        'name': 'Elasticsearch Storer',
        'class': storers.ElasticStorer
    }
    log_storer_status(code='elastic', status='enabled')
except:
    log_storer_status(code='elastic', status='disabled')

print('')

