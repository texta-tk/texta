# import os, sys
# file_dir = os.path.dirname(__file__)
# sys.path.append(file_dir)
# import preprocessors

import logging
from texta.settings import ERROR_LOGGER
from texta.settings import MLP_URL
from texta.settings import SCORO_PREPROCESSOR_ENABLED
from texta.settings import PAASTEAMET_PREPROCESSOR_ENABLED
from task_manager.document_preprocessor.preprocessors import DatePreprocessor
from task_manager.document_preprocessor.preprocessors import MlpPreprocessor
from task_manager.document_preprocessor.preprocessors import TextTaggerPreprocessor
from task_manager.document_preprocessor.preprocessors import MLPLitePreprocessor
from task_manager.document_preprocessor.preprocessors import DatePreprocessor
from task_manager.document_preprocessor.preprocessors import LexTagger
from task_manager.document_preprocessor.preprocessors import ScoroPreprocessor
from task_manager.document_preprocessor.preprocessors import EntityExtractorPreprocessor
from task_manager.document_preprocessor.preprocessors import PaasteametPreprocessor


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
        'name': 'MLP',
        'description': 'Extracts lemmas and identifies language code from multiple languages.',
        'class': MlpPreprocessor,
        'parameters_template': 'preprocessor_parameters/mlp.html',
        'arguments': {
            'mlp_url': MLP_URL,
        },
        'is_enabled': True
    }
    log_preprocessor_status(code='mlp_lite', status='enabled')
except Exception as e:
    logging.getLogger(ERROR_LOGGER).exception(e)
    log_preprocessor_status(code='mlp_lite', status='disabled')

try:
    preprocessor_map['mlp_lite'] = {
        'name': 'MLP Lite',
        'description': 'Extracts lemmas and calculates statistics for classifiers.',
        'class': MLPLitePreprocessor,
        'parameters_template': 'preprocessor_parameters/mlp_lite.html',
        'arguments': {
            'mlp_url': MLP_URL,
        },
        'output_type': ['lemmas', 'full'],
        'field_properties': mlp_field_properties,
        'is_enabled': True
    }
    log_preprocessor_status(code='mlp', status='enabled')
except Exception as e:
    logging.getLogger(ERROR_LOGGER).exception(e)
    log_preprocessor_status(code='mlp', status='disabled')


try:
    preprocessor_map['date_converter'] = {
        'name': 'Date converter',
        'description': 'Converts date field values to correct format',
        'class': DatePreprocessor,
        'parameters_template': 'preprocessor_parameters/date_converter.html',
        'arguments': {},
        'is_enabled': True,
        'languages': ['Estonian', 'English', 'Russian', 'Latvian', 'Lithuanian', 'Other']
    }
    log_preprocessor_status(code='date_converter', status='enabled')
except Exception as e:
    logging.getLogger(ERROR_LOGGER).exception(e)
    log_preprocessor_status(code='date_converter', status='disabled')


try:
    preprocessor_map['text_tagger'] = {
        'name': 'Text Tagger',
        'description': 'Tags documents with TEXTA Text Tagger',
        'class': TextTaggerPreprocessor,
        'parameters_template': 'preprocessor_parameters/text_tagger.html',
        'arguments': {},
        'is_enabled': True
    }
    log_preprocessor_status(code='text_tagger', status='enabled')
except Exception as e:
    logging.getLogger(ERROR_LOGGER).exception(e)
    log_preprocessor_status(code='text_tagger', status='disabled')

try:
    preprocessor_map['lexicon_classifier'] = {
        'name': 'Lexicon Tagger',
        'description': 'Applies lexicon-based tagging',
        'class': LexTagger,
        'parameters_template': 'preprocessor_parameters/lexicon_classifier.html',
        'arguments': {},
        'is_enabled': True,
        'match_types':['Prefix','Exact','Fuzzy'],
        'operations':['OR','AND']
    }
    log_preprocessor_status(code='lexicon_classifier', status='enabled')

except Exception as e:
    logging.getLogger(ERROR_LOGGER).exception(e)
    log_preprocessor_status(code='lexicon_classifier', status='disabled')


try:
    preprocessor_map['scoro'] = {
        'name': 'Scoro',
        'description': 'Extracts topics and evaluates sentiment',
        'class': ScoroPreprocessor,
        'parameters_template': 'preprocessor_parameters/scoro.html',
        'arguments': {},
        'is_enabled': SCORO_PREPROCESSOR_ENABLED,
        'sentiment_lexicons':['Scoro','General','Custom'],
        'sentiment_analysis_methods':['Lexicon-based','Model-based'],
        'scoring_functions':['Mutual information','Chi square','GND','JLG'],
        'bg_favors': ['Doc','All']
    }
    log_preprocessor_status(code='scoro', status='enabled')
except Exception as e:
    logging.getLogger(ERROR_LOGGER).exception(e)
    log_preprocessor_status(code='scoro', status='disabled')

try:
    preprocessor_map['entity_extractor'] = {
        'name': 'Entity Extractor',
        'description': 'Extract entities from documents with TEXTA Entity Extractor',
        'class': EntityExtractorPreprocessor,
        'parameters_template': 'preprocessor_parameters/entity_extractor.html',
        'arguments': {},
        'is_enabled': True
    }
    log_preprocessor_status(code='entity_extractor', status='enabled')
except Exception as e:
    print(e)
    log_preprocessor_status(code='entity_extractor', status='disabled')

try:
    preprocessor_map['paasteamet'] = {
        'name': 'Paasteamet',
        'description': 'Extracts information from PA regulations',
        'class': PaasteametPreprocessor,
        'parameters_template': 'preprocessor_parameters/paasteamet.html',
        'arguments': {},
        'is_enabled': PAASTEAMET_PREPROCESSOR_ENABLED
    }
    log_preprocessor_status(code='paasteamet', status='enabled')

except Exception as e:
    logging.getLogger(ERROR_LOGGER).exception(e)
    log_preprocessor_status(code='paasteamet', status='disabled')

PREPROCESSOR_INSTANCES = {
    preprocessor_code: preprocessor['class'](**preprocessor['arguments'])
    for preprocessor_code, preprocessor in preprocessor_map.items() if preprocessor['is_enabled']
}
