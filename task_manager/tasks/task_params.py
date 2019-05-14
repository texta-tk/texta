import logging
import json
from task_manager.tasks.workers.language_model_worker import LanguageModelWorker
from task_manager.tasks.workers.text_tagger_worker import TagModelWorker
from task_manager.tasks.workers.neuroclassifier.neuroclassifier_worker import NeuroClassifierWorker
from task_manager.tasks.workers.entity_extractor_worker import EntityExtractorWorker
from task_manager.tasks.workers.preprocessor_worker import PreprocessorWorker
from task_manager.tasks.workers.management_workers.management_worker import ManagementWorker
from utils.es_manager import ES_Manager
from texta.settings import ERROR_LOGGER, INFO_LOGGER
from task_manager.tasks.workers.management_workers.management_task_params import ManagerKeys
from task_manager.tasks.task_types import TaskTypes
from task_manager.tasks.workers.neuroclassifier.neuro_models import NeuroModels

fact_names = {}

task_params = [
    {
        "name": "Train Language Model",
        "id": TaskTypes.TRAIN_MODEL.value,
        "template": "task_parameters/train_model.html",
        "result_template": "task-results/train-model-results.html",
        "worker": LanguageModelWorker,
        "allowed_actions": ["delete", "save"]
    },
    {
        "name": "Train Text Tagger",
        "id": TaskTypes.TRAIN_TAGGER.value,
        "template": "task_parameters/train_tagger.html",
        "result_template": "task-results/train-tagger-results.html",
        "worker": TagModelWorker,
        "allowed_actions": ["delete"]
    },
    {
        "name":            "Train Neuroclassifier",
        "id":               TaskTypes.TRAIN_NEUROCLASSIFIER.value,
        "template":        "task_parameters/train_neuroclassifier.html",
        "result_template": "task-results/train-neuroclassifier-results.html",
        "worker":           NeuroClassifierWorker,
        "architectures":    NeuroModels.model_names,
        "allowed_actions": ["delete"]
    },
    {
        "name": "Train Entity Extractor",
        "id": TaskTypes.TRAIN_ENTITY_EXTRACTOR.value,
        "template": "task_parameters/train_entity_extractor.html",
        "result_template": "task-results/train-entity-extractor-results.html",
        "worker": EntityExtractorWorker,
        "facts": fact_names,
        "allowed_actions": ["delete"]
    },
    {
        "name": "Apply Preprocessor",
        "id": TaskTypes.APPLY_PREPROCESSOR.value,
        "template": "task_parameters/apply_preprocessor.html",
        "result_template": "task-results/apply-preprocessor-results.html",
        "worker": PreprocessorWorker,
        "allowed_actions": []
    },
    {
        "name": "Management Task",
        "id": TaskTypes.MANAGEMENT_TASK.value,
        "template": "task_parameters/management_task.html",
        "result_template": "task-results/management-task-results.html",
        "worker": ManagementWorker,
        "enabled_sub_managers": [
            {"key": ManagerKeys.FACT_DELETER.value,
             "name": "Fact Deleter",
             "parameters_template": "management_parameters/fact_deleter.html",
             "facts": fact_names,
             },
        ],
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
                    fact_data[fact['key']].append({'value': val['key'], 'count': val['doc_count']})
            fact_names.update(fact_data)

    except Exception as e:
        active_datasets = [(ds.id, ds.index) for ds in es_m.active_datasets]
        log_dict = {'task': 'GET TASK PARAMS', 'event': 'get_fact_names', 'data': {'active_datasets_ids_and_names': active_datasets, 'response_keys': list(response.keys())}}
        logging.getLogger(ERROR_LOGGER).exception(log_dict, exc_info=True)


def activate_task_worker(task_type):
    for task_param in task_params:
        log_dict = {'task': 'check_task_params', 'data': {'task_param_id': task_param['id'], 'task_type': task_type, 'is_equal': task_param['id'] == task_type}}
        logging.getLogger(INFO_LOGGER).info("Activates task worker", extra=log_dict)
        # Instantiate worker
        worker_instance = task_param['worker']()
        return worker_instance

    return None
