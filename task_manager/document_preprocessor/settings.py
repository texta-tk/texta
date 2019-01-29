# import os, sys
# file_dir = os.path.dirname(__file__)
# sys.path.append(file_dir)
# import preprocessors

import logging
from texta.settings import ERROR_LOGGER
from texta.settings import DATASET_IMPORTER
from texta.settings import SCORO_PREPROCESSOR_ENABLED
from task_manager.document_preprocessor.preprocessors import CommentPreprocessor
from task_manager.document_preprocessor.preprocessors import DatePreprocessor
from task_manager.document_preprocessor.preprocessors import MlpPreprocessor
from task_manager.document_preprocessor.preprocessors import TextTaggerPreprocessor
from task_manager.document_preprocessor.preprocessors import MlpPreprocessor
from task_manager.document_preprocessor.preprocessors import DatePreprocessor
from task_manager.document_preprocessor.preprocessors import LexTagger
from task_manager.document_preprocessor.preprocessors import ScoroPreprocessor
from task_manager.document_preprocessor.preprocessors import EntityExtractorPreprocessor


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
    logging.getLogger(ERROR_LOGGER).exception(e)
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
    logging.getLogger(ERROR_LOGGER).exception(e)
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
    logging.getLogger(ERROR_LOGGER).exception(e)
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
    logging.getLogger(ERROR_LOGGER).exception(e)
    log_preprocessor_status(code='lexicon_classifier', status='disabled')

try:
    preprocessor_map['comment_preprocessor'] = {
        'name': 'Comment preprocessor',
        'description': 'Converts comments',
        'class': CommentPreprocessor,
        'parameters_template': 'parameters/preprocessor_parameters/comment_preprocessor.html',
        'arguments': {},
        'is_enabled': True
    }
    log_preprocessor_status(code='comment_preprocessor', status='enabled')
except Exception as e:
    logging.getLogger(ERROR_LOGGER).exception(e)
    log_preprocessor_status(code='comment_preprocessor', status='disabled')

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
    logging.getLogger(ERROR_LOGGER).exception(e)
    log_preprocessor_status(code='scoro', status='disabled')

try:
    preprocessor_map['entity_extractor'] = {
        'name': 'Entity Extractor preprocessor',
        'description': 'Extract entities from documents with TEXTA Entity Extractor',
        'class': EntityExtractorPreprocessor,
        'parameters_template': 'parameters/preprocessor_parameters/entity_extractor.html',
        'arguments': {},
        'is_enabled': True
    }
    log_preprocessor_status(code='entity_extractor', status='enabled')
except Exception as e:
    print(e)
    log_preprocessor_status(code='entity_extractor', status='disabled')


PREPROCESSOR_INSTANCES = {
    preprocessor_code: preprocessor['class'](**preprocessor['arguments'])
    for preprocessor_code, preprocessor in preprocessor_map.items() if preprocessor['is_enabled']
}
