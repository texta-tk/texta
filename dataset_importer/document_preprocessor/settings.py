import os, sys
file_dir = os.path.dirname(__file__)
sys.path.append(file_dir)
import preprocessors
from texta.settings import DATASET_IMPORTER


mlp_field_properties = {'properties': {'text': {'type':'text',
                                                            'fields': {'keyword': {'type': 'keyword', 'ignore_above': 256}}
                                                        },
                                               'lemmas':{'type':'text',
                                                            'fields': {'keyword': {'type': 'keyword', 'ignore_above': 256}}
                                                        },
                                               'lang':{'type': 'keyword', 'ignore_above': 256}
                                               }
                               }



def log_preprocessor_status(code, status):
    print('[Dataset Importer] {code} preprocessor {status}.'.format(**{'code': code, 'status': status}))


preprocessor_map = {}

try:
    preprocessor_map['mlp'] = {
        'name': 'Multilingual preprocessor',
        'description': 'Extracts lemmas and identifies language code from multiple languages.',
        'class': preprocessors.mlp.MlpPreprocessor,
        'parameters_template': 'parameters/preprocessor_parameters/mlp.html',
        'arguments': {
            'mlp_url': DATASET_IMPORTER['urls']['mlp'],
            'enabled_features': ['text', 'lang', 'texta_facts'],
        },
        'field_properties': mlp_field_properties,
        'is_enabled': True
    }
    log_preprocessor_status(code='mlp', status='enabled')
    
except:
    log_preprocessor_status(code='mlp', status='disabled')

try:
    preprocessor_map['date_converter'] = {
        'name': 'Date conversion preprocessor',
        'description': 'Converts date field values to correct format',
        'class': preprocessors.date_converter.DatePreprocessor,
        'parameters_template': 'parameters/preprocessor_parameters/date_converter.html',
        'arguments': {},
        'is_enabled': True,
        'languages':['Estonian','English','Russian','Latvian','Lithuanian','Other']
    }
    log_preprocessor_status(code='date_converter', status='enabled')
    
except Exception as e:
    print(e)
    log_preprocessor_status(code='date_converter', status='disabled')

print('')
