
from .workers.language_model_worker import LanguageModelWorker
from .workers.tag_model_worker import TagModelWorker
from .workers.entity_extractor_worker import EntityExtractorWorker
from .workers.preprocessor_worker import PreprocessorWorker


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
        "allowed_actions": ["delete", "save"]
    },
    {
        "name":            "Train Entity Extractor",
        "id":              "train_entity_extractor",
        "template":        "task_parameters/train_entity_extractor.html",
        "result_template": "task-results/train-entity-extractor-results.html",
        "worker":           EntityExtractorWorker,
        "allowed_actions": ["delete", "save"]
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


def activate_task_worker(task_type):
    for task_param in task_params:
        if task_param['id'] == task_type:
            worker_instance = task_param['worker']()
            return worker_instance
    return None
