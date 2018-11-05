
from .workers.language_model_worker import LanguageModelWorker
from .workers.tag_model_worker import TagModelWorker
from .workers.preprocessor_worker import PreprocessorWorker


task_params = [
    {
        "name":            "Train Language Model",
        "id":              "train_model",
        "template":        "task_parameters/train_model.html",
        "worker":           LanguageModelWorker,
        "allowed_actions": ["delete", "save"]
    },
    {
        "name":            "Train Text Tagger",
        "id":              "train_tagger",
        "template":        "task_parameters/train_tagger.html",
        "worker":           TagModelWorker,
        "allowed_actions": ["delete", "save"]
    },
    {
        "name":            "Apply Preprocessor",
        "id":              "apply_preprocessor",
        "template":        "task_parameters/apply_preprocessor.html",
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
