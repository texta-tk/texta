import storers


def log_storer_status(code, status):
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

