import logging
import json
from .workers.language_model_worker import LanguageModelWorker
from .workers.text_tagger_worker import TagModelWorker
from .workers.entity_extractor_worker import EntityExtractorWorker
from .workers.preprocessor_worker import PreprocessorWorker
from utils.es_manager import ES_Manager
from texta.settings import ERROR_LOGGER

fact_names = {}

task_params = [
    {
        "name":            "Train Language Model",
        "id":              "train_model",
        "template":        "task_parameters/train_model.html",
        "result_template": "task-results/train-model-results.html",
        "worker":           LanguageModelWorker,
        "allowed_actions": ["delete", "save"]
    },
    {
        "name":            "Train Text Tagger",
        "id":              "train_tagger",
        "template":        "task_parameters/train_tagger.html",
        "result_template": "task-results/train-tagger-results.html",
        "worker":           TagModelWorker,
        "allowed_actions": ["delete"]
    },
    {
        "name":            "Train Entity Extractor",
        "id":              "train_entity_extractor",
        "template":        "task_parameters/train_entity_extractor.html",
        "result_template": "task-results/train-entity-extractor-results.html",
        "worker":          EntityExtractorWorker,
        "facts":           fact_names,
        "allowed_actions": ["delete"]
    },
    {
        "name":            "Apply Preprocessor",
        "id":              "apply_preprocessor",
        "template":        "task_parameters/apply_preprocessor.html",
        "result_template": "task-results/apply-preprocessor-results.html",
        "worker":          PreprocessorWorker,
        "allowed_actions": []
    }
]


def get_fact_names(es_m):
    try:
        fact_names.clear()
        aggs = {'main': {'aggs': {"facts": {"nested": {"path": "texta_facts"}, "aggs": {"fact_names": {"terms": {"field": "texta_facts.fact", "size": 10000}, "aggs": {"fact_values": {"terms": {"field": "texta_facts.str_val"}}}}}}}}}
        es_m.load_combined_query(aggs)
        response = es_m.search()
        # Check if aggregations in response, then check if facts in response['aggregations']
        if ('aggregations' in response) and ('facts' in response['aggregations']) and ('fact_names' in response['aggregations']['facts']):
            response_aggs = response['aggregations']['facts']['fact_names']['buckets']
            fact_data = {}
            for fact in response_aggs:
                fact_data[fact['key']] = []
                for val in fact['fact_values']['buckets']:
                    fact_data[fact['key']].append(val['key'])
            fact_names.update(fact_data)
    except Exception as e:
        logging.getLogger(ERROR_LOGGER).exception(json.dumps(
            {'process': 'GET TASK PARAMS', 'event': 'get_fact_names', 'data': {'active_datasets_ids_and_names': [(ds.id, ds.index) for ds in es_m.active_datasets], 'response_keys': list(response.keys())}}), exc_info=True)


def activate_task_worker(task_type):
    for task_param in task_params:
        if task_param['id'] == task_type:
            worker_instance = task_param['worker']()
            return worker_instance
    return None