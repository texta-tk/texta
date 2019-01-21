# import os, sys
# file_dir = os.path.dirname(__file__)
# sys.path.append(file_dir)
# import preprocessors

from texta.settings import DATASET_IMPORTER
from texta.settings import SCORO_PREPROCESSOR_ENABLED
from texta.settings import PAASTEAMET_PREPROCESSOR_ENABLED
from dataset_importer.document_preprocessor.preprocessors import TextCleanerPreprocessor
from dataset_importer.document_preprocessor.preprocessors import DatePreprocessor
from dataset_importer.document_preprocessor.preprocessors import MlpPreprocessor
from dataset_importer.document_preprocessor.preprocessors import TextTaggerPreprocessor
from dataset_importer.document_preprocessor.preprocessors import MlpPreprocessor
from dataset_importer.document_preprocessor.preprocessors import DatePreprocessor
from dataset_importer.document_preprocessor.preprocessors import LexTagger
from dataset_importer.document_preprocessor.preprocessors import ScoroPreprocessor
from dataset_importer.document_preprocessor.preprocessors import PaasteametPreprocessor


mlp_field_properties = {
    'properties': {
        'text': {
            'type': 'text',
            'fields': {
                'keyword': {
                    'type': 'keyword',
                    'ignore_above': 256
                }
            }
        },
        'lemmas': {
            'type': 'text',
            'fields': {
                'keyword': {
                    'type': 'keyword',
                    'ignore_above': 256
                }
            }
        },
        'lang': {
            'type': 'keyword',
            'ignore_above': 256
        }
    }
}


def log_preprocessor_status(code, status):
    # only print if status disabled
    if status == 'disabled':
        print('[Dataset Importer] {code} preprocessor {status}.'.format(**{'code': code, 'status': status}))


preprocessor_map = {}

try:
    preprocessor_map['mlp'] = {
        'name': 'Multilingual preprocessor',
        'description': 'Extracts lemmas and identifies language code from multiple languages.',
        'class': MlpPreprocessor,
        'parameters_template': 'parameters/preprocessor_parameters/mlp.html',
        'arguments': {
            'mlp_url': DATASET_IMPORTER['urls']['mlp'],
            'enabled_features': ['text', 'lang', 'texta_facts'],
        },
        'field_properties': mlp_field_properties,
        'is_enabled': True
    }
    log_preprocessor_status(code='mlp', status='enabled')
except Exception as e:
    print(e)
    log_preprocessor_status(code='mlp', status='disabled')


try:
    preprocessor_map['date_converter'] = {
        'name': 'Date conversion preprocessor',
        'description': 'Converts date field values to correct format',
        'class': DatePreprocessor,
        'parameters_template': 'parameters/preprocessor_parameters/date_converter.html',
        'arguments': {},
        'is_enabled': True,
        'languages': ['Estonian', 'English', 'Russian', 'Latvian', 'Lithuanian', 'Other']
    }
    log_preprocessor_status(code='date_converter', status='enabled')
except Exception as e:
    print(e)
    log_preprocessor_status(code='date_converter', status='disabled')


try:
    preprocessor_map['text_tagger'] = {
        'name': 'Text Tagger preprocessor',
        'description': 'Tags documents with TEXTA Text Tagger',
        'class': TextTaggerPreprocessor,
        'parameters_template': 'parameters/preprocessor_parameters/text_tagger.html',
        'arguments': {},
        'is_enabled': True
    }
    log_preprocessor_status(code='text_tagger', status='enabled')
except Exception as e:
    print(e)
    log_preprocessor_status(code='text_tagger', status='disabled')

try:
    preprocessor_map['lexicon_classifier'] = {
        'name': 'Lexicon Tagger Preprocessor',
        'description': 'Applies lexicon-based tagging',
        'class': LexTagger,
        'parameters_template': 'parameters/preprocessor_parameters/lexicon_classifier.html',
        'arguments': {},
        'is_enabled': True,
        'match_types':['Prefix','Exact','Fuzzy'],
        'operations':['OR','AND']
    }
    log_preprocessor_status(code='lexicon_classifier', status='enabled')

except Exception as e:
    print(e)
    log_preprocessor_status(code='lexicon_classifier', status='disabled')

try:
    preprocessor_map['text_cleaner'] = {
        'name': 'Text Cleaner preprocessor',
        'description': 'Cleans texts for classification',
        'class': TextCleanerPreprocessor,
        'parameters_template': 'parameters/preprocessor_parameters/text_cleaner.html',
        'arguments': {},
        'is_enabled': True
    }
    log_preprocessor_status(code='text_cleaner', status='enabled')
except Exception as e:
    print(e)
    log_preprocessor_status(code='text_cleaner', status='disabled')

try:
    preprocessor_map['scoro'] = {
        'name': 'Scoro preprocessor',
        'description': 'Extracts topics and evaluates sentiment',
        'class': ScoroPreprocessor,
        'parameters_template': 'parameters/preprocessor_parameters/scoro.html',
        'arguments': {},
        'is_enabled': SCORO_PREPROCESSOR_ENABLED,
        'sentiment_lexicons':['Scoro','General','Custom'],
        'sentiment_analysis_methods':['Lexicon-based','Model-based'],
        'scoring_functions':['Mutual information','Chi square','GND','JLG'],
        'bg_favors': ['Doc','All']
    }
    log_preprocessor_status(code='scoro', status='enabled')

except Exception as e:
    print(e)
    log_preprocessor_status(code='scoro', status='disabled')

try:
    preprocessor_map['paasteamet'] = {
        'name': 'Paasteamet preprocessor',
        'description': 'Extracts information from PA regulations',
        'class': PaasteametPreprocessor,
        'parameters_template': 'parameters/preprocessor_parameters/paasteamet.html',
        'arguments': {},
        'is_enabled': PAASTEAMET_PREPROCESSOR_ENABLED
    }
    log_preprocessor_status(code='paasteamet', status='enabled')

except Exception as e:
    print(e)
    log_preprocessor_status(code='paasteamet', status='disabled')

def convert_to_utf8(document):
    """
    Loops through all key, value pairs in dict, checks if it is a string/bytes
    and tries to decode it to utf8.
    :param document: Singular document.
    :return: Singular document decoded into utf8.
    """
    for key, value in document.items():
        if type(value) is bytes:
            document[key] = value.decode('utf8')
    return document


PREPROCESSOR_INSTANCES = {
    preprocessor_code: preprocessor['class'](**preprocessor['arguments'])
    for preprocessor_code, preprocessor in preprocessor_map.items() if preprocessor['is_enabled']
}
