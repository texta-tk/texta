from .workers.language_model_worker import LanguageModelWorker
from .workers.tag_model_worker import TagModelWorker
from .workers.entity_extractor_worker import EntityExtractorWorker
from .workers.preprocessor_worker import PreprocessorWorker
from utils.es_manager import ES_Manager


class TaskParams():
    def __init__(self, es_m):
        self.es_m = es_m
        self.task_params = self._init_task_params()

    def _init_task_params(self):
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
                "facts":            self._get_fact_names(),
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
        return task_params


    def activate_task_worker(self, task_type):
        for task_param in self.task_params:
            if task_param['id'] == task_type:
                worker_instance = task_param['worker']()
                return worker_instance
        return None

    def _get_fact_names(self):
        agg_query = {'main': {'query': {'bool': {'should': [], 'must': [], 'must_not': [], 'minimum_should_match': 0}}, 'aggs':  {'fact': {'nested': {'path': 'texta_facts'}, 'aggs': {'fact': {'terms': {'field': 'texta_facts.fact'}}}}}}, 'facts': {'include': [], 'total_include': 0, 'exclude': [], 'total_exclude': 0}}
        self.es_m.load_combined_query(agg_query)
        response = self.es_m.search()
        import pdb;pdb.set_trace()
        return response