""" The Mass Helper class
"""
import json
from task_manager.models import Task
from task_manager.task_manager import create_task

# Data scroll
MAX_DOCS_PAGE = 5000
# Mass Train Tagger
MIN_DOCS_TAGGED = 100


class MassHelper:
    """ Mass Helper Class

    Provides helper functionality to mass trainer and tagger
    """

    def __init__(self, es_manager):
        self.es_m = es_manager
        self.es_url = es_manager.es_url
        self.index = es_manager.stringify_datasets()

    def _iterate_docs(self, q):
        """ Iterage over all docs for a given query q
        """
        # scroll
        resp = self.es_m.requests.get('{}/{}/_search?scroll=1m'.format(self.es_url, self.index), json=q)
        data = resp.json()
        scroll_id = data['_scroll_id']
        docs = data['hits']['hits']
        while docs:
            # Consume all page docs
            for d in docs:
                yield d
            # Next page
            resp = self.es_m.requests.get('{}/_search/scroll'.format(self.es_url),
                                          json={'scroll': '1m', 'scroll_id': scroll_id})
            data = resp.json()
            scroll_id = data['_scroll_id']
            docs = data['hits']['hits']

    def _get_total(self, q):
        """ Total of documents for a given query q
        """
        resp = self.es_m.requests.get('{}/{}/_count'.format(self.es_url, self.index), json=q)
        data = resp.json()
        total = data['count']
        return total

    def _dict_query_tag_filter(self, tag):
        q = {}
        q['query'] = {}
        q['query']['nested'] = {}
        q['query']['nested']['path'] = "texta_facts"
        q['query']['nested']['query'] = {'term': {"texta_facts.str_val": tag}}
        return q

    def get_unique_tags(self):
        """ Get Unique Tags
        """
        q = {}
        q['query'] = {}
        q['query']['nested'] = {}
        q['query']['nested']['path'] = "texta_facts"
        q['query']['nested']['query'] = {'term': {"texta_facts.fact": "TEXTA_TAG"}}
        q['_source'] = "texta_facts"
        q['size'] = MAX_DOCS_PAGE
        # Get unique tags
        unique_tags = set()
        for doc in self._iterate_docs(q):
            for f in doc['_source']['texta_facts']:
                if f['fact'] == 'TEXTA_TAG':
                    tag = f['str_val']
                    unique_tags.add(tag)
        return unique_tags

    def get_tag_frequency(self, tags):
        """ Get Tags frequency
        """
        tag_freq = {}
        for tag in tags:
            q = self._dict_query_tag_filter(tag)
            c = self._get_total(q)
            tag_freq[tag] = c
        return tag_freq

    def schedule_tasks(self, selected_tags, normalizer_opt, classifier_opt, reductor_opt, extractor_opt, field, dataset_id, user):

        tag_frequency = self.get_tag_frequency(selected_tags)
        retrain_tasks = []
        # Get list of available models
        task_tagger_list = [tagger for tagger in Task.objects.filter(task_type='train_tagger')]
        task_tagger_tag_set = set([tagger.description for tagger in task_tagger_list])

        for task_tagger in task_tagger_list:

            # Get tag label
            tag_label = task_tagger.description
            # Filter models that are not included in the tag_frequency map
            if tag_label not in tag_frequency:
                continue
            # Filter models with less than MIN_DOCS_TAGGED docs
            if tag_frequency.get(tag_label, 0) < MIN_DOCS_TAGGED:
                continue
            # Filter running tasks
            if task_tagger.is_running():
                continue
            # If here, retrain model with tags (re-queue task)
            task_id = task_tagger.pk
            retrain_task = {'task_id': task_id, 'tag': tag_label}
            retrain_tasks.append(retrain_task)

            # Update query parameter from task
            tag_parameters = json.loads(task_tagger.parameters)
            self._add_search_tag_query(tag_parameters, tag_label)
            task_tagger.parameters = json.dumps(tag_parameters)
            task_tagger.requeue_task()

        new_model_tasks = []
        for tag_label in selected_tags:
            # Check if it is a new model
            if tag_label in task_tagger_tag_set:
                continue
            # Filter models with less than MIN_DOCS_TAGGED docs
            if tag_frequency.get(tag_label, 0) < MIN_DOCS_TAGGED:
                continue
            # Build task parameters
            task_param = {}
            task_param["description"] = tag_label
            task_param["normalizer_opt"] = normalizer_opt
            task_param["classifier_opt"] = classifier_opt
            task_param["reductor_opt"] = reductor_opt
            task_param["extractor_opt"] = extractor_opt
            task_param["field"] = field
            task_param["dataset"] = dataset_id
            self._add_search_tag_query(task_param, tag_label)
            # Create execution task
            task_type = "train_tagger"
            task_id = create_task(task_type, tag_label, task_param, user)
            # Add task to queue
            task = Task.get_by_id(task_id)
            task.update_status(Task.STATUS_QUEUED)
            # Add task id to response
            new_model_task = {'task_id': task_id, 'tag': tag_label}
            new_model_tasks.append(new_model_task)

        data = {'retrain_models': retrain_tasks, 'new_models': new_model_tasks}
        return data

    def _add_search_tag_query(self, param_dict, tag_label):
        param_dict['search_tag'] = {}
        param_dict['search_tag']['main'] = {}
        param_dict['search_tag']['main']['query'] = {}
        param_dict['search_tag']['main']['query']['nested'] = {}
        param_dict['search_tag']['main']['query']['nested']['path'] = "texta_facts"
        param_dict['search_tag']['main']['query']['nested']['query'] = {'term': {"texta_facts.str_val": tag_label}}
