import platform
if platform.system() == 'Windows':
    from threading import Thread as Process
else:
    from multiprocessing import Process

from gensim.models import word2vec
from datetime import datetime
import logging
import json
import os

from task_manager.models import Task
from searcher.models import Search
from utils.datasets import Datasets
from utils.es_manager import ES_Manager

from texta.settings import MODELS_DIR, INFO_LOGGER, ERROR_LOGGER

class LanguageModel:

    def __init__(self):
        pass
    
    def train(self, task_params, user, session):
        Process(target=self._training_process,args=(task_params, user, session)).start()
        return True        
    
    def delete(self):
        pass

    @staticmethod
    def _parse_params(task_params, session):
        search_id = task_params['search']

        # select search
        if search_id == 'all_docs':
            query = {"main":{"query":{"bool":{"minimum_should_match":0,"must":[],"must_not":[],"should":[]}}}}
        else:
            query = json.loads(Search.objects.get(pk=int(search_id)).query)

        # set task parameters
        parameters = {'num_dimensions': int(task_params['num_dimensions']),
                      'num_workers': int(task_params['num_workers']),
                      'min_freq': int(task_params['min_freq']),
                      'dataset': int(session['dataset']),
                      'field': json.loads(task_params['field'])['path'],
                      'query': query
                      }
        
        return parameters    
   
    def _training_process(self, task_params, user, session):
        description = task_params['description']
        parameters = self._parse_params(task_params, session)

        # add task to db
        new_task = Task(description = description,
                        parameters = json.dumps(parameters),
                        status = 'running',
                        time_started = datetime.now(),
                        time_completed = None,
                        user = user)
        
        new_task.save()

        logging.getLogger(INFO_LOGGER).info(json.dumps({'process': 'CREATE MODEL', 'event': 'model_training_started', 'data': {'task_id': new_task.id}}))

        num_passes = 5
        # Number of word2vec passes + one pass to vocabulary building
        total_passes = num_passes + 1
        show_progress = ShowProgress(new_task.pk, multiplier=total_passes)
        show_progress.update_view(0)
        model = word2vec.Word2Vec()

        try:
            sentences = esIterator(parameters, session, callback_progress=show_progress)

            model = word2vec.Word2Vec(sentences, min_count=parameters['min_freq'],
                                      size=parameters['num_dimensions'],
                                      workers=parameters['num_workers'],
                                      iter=num_passes)

            model_name = 'model_' + str(new_task.pk)
            output_model_file = os.path.join(MODELS_DIR, model_name)
            model.save(output_model_file)
            task_status = 'completed'

        except Exception as e:
            logging.getLogger(ERROR_LOGGER).error(json.dumps({'process': 'CREATE MODEL', 'event': 'model_training_failed', 'args': {'user_name': user.username}}), exc_info=True)
            print('--- Error: {0}'.format(e))
            task_status = 'failed'

        logging.getLogger(INFO_LOGGER).info(json.dumps({'process': 'CREATE MODEL', 'event': 'model_training_completed', 'data': {'task_id': new_task.id}}))
         # declare the job done
        r = Task.objects.get(pk=new_task.pk)
        r.time_completed = datetime.now()
        r.status = task_status
        r.save()
        print('asd')


class ShowProgress(object):
    """ Show model training progress
    """
    def __init__(self, task_pk, multiplier=None):
        self.n_total = None
        self.n_count = 0
        self.task_pk = task_pk
        self.multiplier = multiplier

    def set_total(self, total):
        self.n_total = total
        if self.multiplier:
            self.n_total = self.multiplier*total

    def update(self, amount):
        if amount == 0:
            return
        self.n_count += amount
        percentage = (100.0*self.n_count)/self.n_total
        self.update_view(percentage)

    def update_view(self, percentage):
        r = Task.objects.get(pk=self.task_pk)
        r.status = 'running [{0:3.0f} %]'.format(percentage)
        r.save()


class esIteratorError(Exception):
    """ esIterator Exception
    """
    pass


class esIterator(object):
    """  ElasticSearch Iterator
    """

    def __init__(self, parameters, session, callback_progress=None):
        self.field = parameters['field']
        # Define selected mapping
        ds = Datasets().activate_dataset(session)
        self.es_m = ds.build_manager(ES_Manager)
        self.es_m.load_combined_query(parameters['query'])
        self.callback_progress = callback_progress

        if self.callback_progress:
            total_elements = self.get_total_documents()
            callback_progress.set_total(total_elements)

    def __iter__(self):
        self.es_m.set_query_parameter('size', 500)
        response = self.es_m.scroll()

        scroll_id = response['_scroll_id']
        l = response['hits']['total']

        while l > 0:
            response = self.es_m.scroll(scroll_id=scroll_id)
            l = len(response['hits']['hits'])
            scroll_id = response['_scroll_id']

            # Check errors in the database request
            if (response['_shards']['total'] > 0 and response['_shards']['successful'] == 0) or response['timed_out']:
                msg = 'Elasticsearch failed to retrieve documents: ' \
                      '*** Shards: {0} *** Timeout: {1} *** Took: {2}'.format(response['_shards'], response['timed_out'], response['took'])
                raise esIteratorError(msg)

            for hit in response['hits']['hits']:
                try:
                    # Take into account nested fields encoded as: 'field.sub_field'
                    decoded_text = hit['_source']
                    for k in self.field.split('.'):
                        decoded_text = decoded_text[k]
                    sentences = decoded_text.split('\n')
                    for sentence in sentences:
                        yield [word.strip().lower() for word in sentence.split(' ')]
                except:
                    # If the field is missing from the document
                    KeyError

            if self.callback_progress:
                self.callback_progress.update(l)

    def get_total_documents(self):
        return self.es_m.get_total_documents()        
