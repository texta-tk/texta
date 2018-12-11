import os
import json
import logging
import numpy as np
import pickle as pkl
from itertools import chain

from task_manager.models import Task
from searcher.models import Search
from utils.es_manager import ES_Manager
from utils.datasets import Datasets

from texta.settings import ERROR_LOGGER
from texta.settings import INFO_LOGGER
from texta.settings import MODELS_DIR

from pycrfsuite import Trainer, Tagger
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelBinarizer
from task_manager.tools import ShowSteps
from task_manager.tools import TaskCanceledException
from task_manager.tools import get_pipeline_builder

from .base_worker import BaseWorker


class EntityExtractorWorker(BaseWorker):

    def __init__(self):
        self.task_id = None
        self.model_name = None
        self.description = None
        self.task_model_obj = None
        self.n_jobs = 1
        
        self.tagger = None
        self.facts = None

    def run(self, task_id):

        self.task_id = task_id
        self.task_model_obj = Task.objects.get(pk=self.task_id)

        task_params = json.loads(self.task_model_obj.parameters)
        steps = ["preparing data", "training", "done"]
        show_progress = ShowSteps(self.task_id, steps)
        show_progress.update_view()
        import pdb;pdb.set_trace()
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
            self.model_name = 'model_{0}'.format(self.task_id)
            hits, raw_facts = self._scroll_query_response(es_m, param_query, fields)
            # Prepare data
            X_train, y_train, X_val, y_val = self._prepare_data(hits, raw_facts)
            # Training the model.
            show_progress.update(1)
            # Train and report validation
            model, report = self._train_and_validate(X_train, y_train, X_val, y_val)
            print(report)
            train_summary = {}
            train_summary['samples'] = len(hits)
            train_summary['model_type'] = 'CRF'
            train_summary.update(report)
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
        print('Done with crf task')


    def convert_and_predict(self, data, task_id):
        self.task_id = task_id
        # Recover features from model to check map
        self._load_tagger()
        self._load_facts()
        data = self._transform(data, self.facts)
        processed_data = (self._sent2features(s) for s in data)
        preds = [self.tagger.tag(x) for x in processed_data]
        return preds


    def _prepare_data(self, hits, raw_facts):
        X_train = []
        X_val = []
        # Split facts for training and testing 
        facts_train, facts_val = train_test_split(raw_facts, test_size=0.1, random_state=42)
        facts_train = self._extract_facts(facts_train)
        facts_val = self._extract_facts(facts_val)
        # Save all facts for later tagging
        all_facts = {**facts_train, **facts_val}
        self._save_as_pkl(all_facts, "meta")
        # Transform data 
        X_train, X_val = train_test_split(hits, test_size=0.1, random_state=42)
        X_train = self._transform(X_train, facts_train)
        X_val = self._transform(X_val, facts_val)
    
        # Create training data generators
        y_train = (self._sent2labels(s) for s in X_train)
        X_train = (self._sent2features(s) for s in X_train)
        y_val = (self._sent2labels(s) for s in X_val)
        X_val = (self._sent2features(s) for s in X_val)
        return X_train, y_train, X_val, y_val 


    def _save_as_pkl(self, var, suffix):
        # Save facts as metadata for tagging, to covert new data into training data using facts
        path = os.path.join(MODELS_DIR, "{}_{}".format(self.model_name, suffix))
        with open(path, "wb") as f:
            pkl.dump(var, f)


    def _extract_facts(self, facts):
        # Create a dict of unique facts, with value as key and name as dict key value
        extracted_facts = {}
        for fact in facts:
            if fact["str_val"] not in extracted_facts:
                extracted_facts[fact["str_val"]] = fact["fact"]
        return extracted_facts


    def _transform(self, data, facts):
        marked_docs = []
        for i, doc in enumerate(data):
            marked = []
            for word in doc.split(' '):
                if word in facts:
                    # If the word is a fact, mark it as so
                    marked.append((word, facts[word]))
                else:
                    # Add no fact, with a special tag
                    marked.append((word, '<TEXTA_O>'))
            marked_docs.append(marked)

            if i % 5000 == 0: # DEBUG
                print(i)
        return marked_docs


    def _word2features(self, sent, i):
        word = sent[i][0]
        # Using strings instead of bool/int to satisfy pycrfsuite
        features = [
            # Bias
            'b',
            #'word.lower='
            word.lower(),
            #'word[-3:]='
            word[-3:],
            #'word[-2:]='
            word[-2:],
            #'word.isupper=%s' % 
            '1' if word.isupper() else '0',
            #'word.istitle=%s' % 
            '1' if word.istitle() else '0',
            #'word.isdigit=%s' % 
            '1' if word.isdigit() else '0']

        if i > 0:
            word1 = sent[i-1][0]
            features.extend([
                #'-1:word.lower=' + 
                word1.lower(),
                #'-1:word.istitle=%s' % 
                '1' if word1.istitle() else '0',
                #'-1:word.isupper=%s' % 
                '1' if word1.isupper() else '0',
            ])
        else:
            features.append('BOS')
            
        if i < len(sent)-1:
            word1 = sent[i+1][0]
            features.extend([
                #'+1:word.lower=' + 
                word1.lower(),
                #'+1:word.istitle=%s' % 
                '1' if word1.istitle() else '0',
                # '+1:word.isupper=%s' % 
                '1' if word1.isupper() else '0'])
        else:
            features.append('<TEXTA_EOS>')
        return features


    def _sent2features(self, sent, facts=None):
        return (self._word2features(sent, i) for i in range(len(sent)))


    def _sent2labels(self, sent):
        return (label for token, label in sent)


    def _sent2tokens(self, sent):
        return (token for token, label in sent)


    def _train_and_validate(self, X_train, y_train, X_val, y_val):
        model = self._train_and_save(X_train, y_train)
        # Initialize self.tagger
        self._load_tagger()
        report = self._validate(self.tagger, X_val, y_val)
        return model, report


    def _load_facts(self):
        file_path = os.path.join(MODELS_DIR, "{}_{}".format(self.model_name, "meta"))
        with open(file_path, "rb") as f:
            self.facts = pkl.load(f)


    def _load_tagger(self):
        self.model_name = 'model_{0}'.format(self.task_id)
        file_path = os.path.join(MODELS_DIR, self.model_name)
        try:
            tagger = Tagger()
            tagger.open(file_path)
        except Exception as e:
            print(e)
            logging.getLogger(ERROR_LOGGER).error('Failed to load crf model from the filesystem.', exc_info=True, extra={
                'model_name': self.model_name,
                'file_path':  file_path})

        self.tagger = tagger
        return self.tagger


    def _train_and_save(self, X_train, y_train):
        trainer = Trainer(verbose=False)

        for xseq, yseq in zip(X_train, y_train):
            trainer.append(xseq, yseq)
        trainer.set_params({
            'c1': 1.0,   # coefficient for L1 penalty
            'c2': 1e-3,  # coefficient for L2 penalty
            'max_iterations': 50,  # stop earlier
            # transitions that are possible, but not observed
            'feature.possible_transitions': True})

        self.model_name = 'model_{0}'.format(self.task_id)
        output_model_file = os.path.join(MODELS_DIR, self.model_name)
        # Train and save
        trainer.train(output_model_file)
        return trainer


    def _bio_classification_report(self, y_true, y_pred):
        """
        Classification report for a list of BIO-encoded sequences.
        It computes token-level metrics and discards "<TEXTA_O>" labels.
        """
        lb = LabelBinarizer()
        y_true_combined = lb.fit_transform(list(chain.from_iterable(y_true)))
        y_pred_combined = lb.transform(list(chain.from_iterable(y_pred)))

        tagset = set(lb.classes_) - {'<TEXTA_O>'}
        tagset = sorted(tagset, key=lambda tag: tag.split('-', 1)[::-1])
        class_indices = {cls: idx for idx, cls in enumerate(lb.classes_)}

        # Return sklearn classification_report, return report as dict
        return classification_report(
            y_true_combined,
            y_pred_combined,
            labels=[class_indices[cls] for cls in tagset],
            target_names=tagset,
            output_dict=True)


    def _validate(self, model, X_val, y_val):
        y_pred = [model.tag(xseq) for xseq in X_val]
        report = self._bio_classification_report(y_val, y_pred)
        return report


    def _scroll_query_response(self, es_m, query, fields):
        # Scroll the search, extract facts
        hits = []
        facts = []
        es_m.load_combined_query(query)
        response = es_m.scroll()
        scroll_id = response['_scroll_id']
        total_docs = response['hits']['total']
        while total_docs > 0:
            for hit in response['hits']['hits']:
                source = hit['_source']
                for field in fields:
                    content = source
                    if 'texta_facts' in content:
                        facts.extend(content['texta_facts'])
                    for sub_f in field.split('.'):
                        content = content[sub_f]
                    hits.append(content)
            response = es_m.scroll(scroll_id=scroll_id)
            total_docs = len(response['hits']['hits'])
            scroll_id = response['_scroll_id']
        return hits, facts
