import os, sys
file_dir = os.path.dirname(__file__)
sys.path.append(file_dir)
import extractors


def log_extractor_status(code, status):
    if status == 'disabled':
        print('[Dataset Importer] {code} extractor {status}.'.format(**{'code': code, 'status': status}))


extractor_map = {}

try:
    extractor_map['zip'] = {
        'name': 'ZIP',
        'parameter_tags': 'file',
        'type': 'archive',
        'class': extractors.zip.ZipExtractor
    }
    log_extractor_status(code='.zip', status='enabled')
except:
    log_extractor_status(code='.zip', status='disabled')

try:
    extractor_map['tar'] = {
        'name': 'TAR/TAR.GZ',
        'parameter_tags': 'file',
        'type': 'archive',
        'class': extractors.tar.TarExtractor
    }
    log_extractor_status(code='.tar', status='enabled')
except:
    log_extractor_status(code='.tar', status='disabled')

print('')
