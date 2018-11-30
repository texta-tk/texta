import os
import json
import logging
import numpy as np

from task_manager.models import Task
from task_manager.tools import EsDataSample
from searcher.models import Search
from utils.es_manager import ES_Manager
from utils.datasets import Datasets

from texta.settings import ERROR_LOGGER
from texta.settings import INFO_LOGGER
from texta.settings import MODELS_DIR

from sklearn.model_selection import train_test_split
from task_manager.tools import ShowSteps
from task_manager.tools import TaskCanceledException
from task_manager.tools import get_pipeline_builder

from .base_worker import BaseWorker


class EntityExtractorWorker(BaseWorker):

    def __init__(self):
        self.task_id = None
        self.model = None
        self.model_name = None
        self.description = None
        self.task_model_obj = None
        self.n_jobs = 1

    def run(self, task_id):

        self.task_id = task_id
        self.task_model_obj = Task.objects.get(pk=self.task_id)

        task_params = json.loads(self.task_model_obj.parameters)
        steps = ["preparing data", "training", "done"]
        show_progress = ShowSteps(self.task_id, steps)
        show_progress.update_view()

        if 'num_threads' in task_params:
            self.n_jobs = int(task_params['num_threads'])

        try:
            if 'fields' in task_params:
                fields = task_params['fields']
            else:
                fields = [task_params['field']]

            show_progress.update(0)

            # Check if query was explicitly set
            if 'search_tag' in task_params:
                # Use set query
                param_query = task_params['search_tag']
            else:
                # Otherwise, load query from saved search
                param_query = json.loads(Search.objects.get(pk=int(task_params['search'])).query)

            # Build Data sampler
            ds = Datasets().activate_datasets_by_id(task_params['dataset'])
            es_m = ds.build_manager(ES_Manager)

            # Prepare data
            X_train, y_train, X_val, y_val = self._prepare_data(fields)
            # Training the model.
            show_progress.update(1)
            ######TODO TRAIN ######
            model, report = self._train_and_validate(X_train, y_train, X_val, y_val)
            train_summary['samples'] = report

            train_summary['model_type'] = 'CRF'
            show_progress.update(2)

            # Declare the job as done
            r = Task.objects.get(pk=self.task_id)
            r.result = json.dumps(train_summary)
            r.update_status(Task.STATUS_COMPLETED, set_time_completed=True)

            logging.getLogger(INFO_LOGGER).info(json.dumps({
                'process': 'CREATE CRF MODEL',
                'event':   'crf_training_completed',
                'data':    {'task_id': self.task_id}
            }))

        except TaskCanceledException as e:
            # If here, task was canceled while training
            # Delete task
            task = Task.objects.get(pk=self.task_id)
            task.delete()
            logging.getLogger(INFO_LOGGER).info(json.dumps({'process': 'CREATE CLASSIFIER', 'event': 'crf_training_canceled', 'data': {'task_id': self.task_id}}), exc_info=True)
            print("--- Task canceled")

        except Exception as e:
            logging.getLogger(ERROR_LOGGER).exception(json.dumps(
                {'process': 'CREATE CLASSIFIER', 'event': 'crf_training_failed', 'data': {'task_id': self.task_id}}), exc_info=True)
            # declare the job as failed.
            task = Task.objects.get(pk=self.task_id)
            task.result = json.dumps({'error': repr(e)})
            task.update_status(Task.STATUS_FAILED, set_time_completed=True)
        
        print('done')

    def convert_and_predict(self, data):
        # Recover features from model to check map
        data = self._transform(text_map)
        processed_data = (self._sent2features(s) for s in text_map)

        tagger = self._load_tagger(task_id)
        preds = tagger.tag(processed_data)

        return preds


    def _prepare_data(self, fields):
        X_train, X_val = train_test_split(self.data, test_size=0.1, random_state=42)
        facts_train = self._extract_facts(X_train)
        facts_val = self._extract_facts(X_val)
        X_train = self._transform(X_train, facts_train, fields)
        X_val = self._transform(X_val, facts_val, fields)

        y_train = (self._sent2labels(s) for s in X_train)
        X_train = (self._sent2features(s) for s in X_train)
        y_val = (self._sent2labels(s) for s in X_val)
        X_val = (self._sent2features(s) for s in X_val)
        return X_train, y_train, X_val, y_val 


    def _extract_facts(self, data):
        facts = {}
        for doc in data:
            if "texta_facts" in doc["_source"]:
                for fact in doc["_source"]["texta_facts"]:
                    if fact["str_val"] not in facts:
                        facts[fact["str_val"]] = fact["fact"]
        return facts


    def _transform(self, data, facts, fields):
        marked_docs = []
        for i, doc in enumerate(data):
            marked = []
            if 'texta_facts' in doc['_source']:
                if len(fields.split('.')) > 1:
                    content = doc['_source'] 
                    for key in len(fields.split('.')):
                        content = content[key]
                else:
                    content = doc['_source'][fields]

                for word in content.split(' '):
                    if word in facts:
                        marked.append((word, facts[word]))
                    else:
                        marked.append((word, 'O'))
                marked_docs.append(marked)

            if i % 5000 == 0:
                print(i)

        return marked_docs


    def _word2features(self, sent, i):
        word = sent[i][0]
        postag = sent[i][1]
        features = [
            'bias',
            'word.lower=' + word.lower(),
            'word[-3:]=' + word[-3:],
            'word[-2:]=' + word[-2:],
            'word.isupper=%s' % word.isupper(),
            'word.istitle=%s' % word.istitle(),
            'word.isdigit=%s' % word.isdigit()]
        
        if i > 0:
            word1 = sent[i-1][0]
            features.extend([
                '-1:word.lower=' + word1.lower(),
                '-1:word.istitle=%s' % word1.istitle(),
                '-1:word.isupper=%s' % word1.isupper(),
            ])
        else:
            features.append('BOS')
            
        if i < len(sent)-1:
            word1 = sent[i+1][0]
            features.extend([
                '+1:word.lower=' + word1.lower(),
                '+1:word.istitle=%s' % word1.istitle(),
                '+1:word.isupper=%s' % word1.isupper()])
        else:
            features.append('EOS')
        return features


    def _sent2features(self, sent, facts=None):
        return (self._word2features(sent, i) for i in range(len(sent)))


    def _sent2labels(self, sent):
        return (label for token, label in sent)


    def _sent2tokens(self, sent):
        return (token for token, label in sent)


    def _train_and_validate(self, X_train, y_train, X_val, y_val):
        model = self._train_and_save(X_train, y_train)
        tagger = self._load_tagger(self.task_id)
        report = self._validate(tagger, X_val, y_val)
        return model, report


    def _load_tagger(self, task_id):
        model_name = 'model_{0}'.format(task_id)
        file_path = os.path.join(MODELS_DIR, model_name)

        try:
            tagger = pycrfsuite.Tagger()
            tagger.open(file_path)
        except Exception as e:
            logging.getLogger(ERROR_LOGGER).error('Failed to load crf model from the filesystem.', exc_info=True, extra={
                'model_name': model_name,
                'file_path':  file_path
            })

        return tagger


    def _train_and_save(self, X_train, y_train):
        trainer = pycrfsuite.Trainer(verbose=False)

        for xseq, yseq in zip(X_train, y_train):
            trainer.append(xseq, yseq)
        trainer.set_params({
            'c1': 1.0,   # coefficient for L1 penalty
            'c2': 1e-3,  # coefficient for L2 penalty
            'max_iterations': 50,  # stop earlier

            # transitions that are possible, but not observed
            'feature.possible_transitions': True})

        model_name = 'model_{0}'.format(self.task_id)
        output_model_file = os.path.join(MODELS_DIR, model_name)
        # Train and save
        trainer.train(output_model_file)

        return trainer


    def _bio_classification_report(self, y_true, y_pred):
        """
        Classification report for a list of BIO-encoded sequences.
        It computes token-level metrics and discards "O" labels.
        
        Note that it requires scikit-learn 0.15+ (or a version from github master)
        to calculate averages properly!
        """
        lb = LabelBinarizer()
        y_true_combined = lb.fit_transform(list(chain.from_iterable(y_true)))
        y_pred_combined = lb.transform(list(chain.from_iterable(y_pred)))
            
        tagset = set(lb.classes_) - {'O'}
        tagset = sorted(tagset, key=lambda tag: tag.split('-', 1)[::-1])
        class_indices = {cls: idx for idx, cls in enumerate(lb.classes_)}
        
        return classification_report(
            y_true_combined,
            y_pred_combined,
            labels = [class_indices[cls] for cls in tagset],
            target_names = tagset,
        )


    def _validate(self, model, X_val, y_val):
        y_pred = [model.tag(xseq) for xseq in X_val]
        report = self._bio_classification_report(y_val, y_pred)
        return report