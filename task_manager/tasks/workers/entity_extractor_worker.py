import os
import sys
import json
import logging
import numpy as np
import pickle as pkl
import psutil
from itertools import chain, product

from task_manager.models import Task
from searcher.models import Search
from utils.es_manager import ES_Manager
from utils.datasets import Datasets

from texta.settings import ERROR_LOGGER, INFO_LOGGER, MODELS_DIR, URL_PREFIX, MEDIA_URL, PROTECTED_MEDIA, FACT_FIELD
from utils.helper_functions import plot_confusion_matrix, create_file_path
import pandas as pd

from pycrfsuite import Trainer, Tagger
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.preprocessing import LabelBinarizer, MultiLabelBinarizer

from task_manager.tools import ShowSteps
from task_manager.tools import TaskCanceledException
from task_manager.tools import get_pipeline_builder

from .base_worker import BaseWorker


class EntityExtractorWorker(BaseWorker):

    def __init__(self):
        self.es_m = None
        self.task_id = None
        self.model_name = None
        self.description = None
        self.task_obj = None
        self.task_type = None
        self.task_params = None
        self.n_jobs = 1
        
        self.tagger = None
        self.facts = None
        self.oob_val = "<TEXTA_O>"
        self.fact_keyword_val = "<TEXTA_FACT>"
        self.eos_val = "<TEXTA_BOS>"
        self.bos_val = "<TEXTA_EOS>"
        self.train_summary = {}
        # If there is less than this amount of memory in Mb left in the machine, stop appending training data
        self.min_mb_available_memory = 1500

    def run(self, task_id):

        self.task_id = task_id
        self.task_obj = Task.objects.get(pk=self.task_id)
        self.task_type = self.task_obj.task_type

        self.task_params = json.loads(self.task_obj.parameters)
        steps = ["preparing data", "training", "done"]
        show_progress = ShowSteps(self.task_id, steps)
        show_progress.update_view()
        if 'num_threads' in self.task_params:
            self.n_jobs = int(self.task_params['num_threads'])

        try:
            if "facts" in self.task_params:
                fact_names = self.task_params["facts"]
            else:
                self._bad_params_result("No fact names given")
                return False

            show_progress.update(0)

            search = self.task_params['search']
            # select search
            if search == 'all_docs':
                param_query = {"main": {"query": {"bool": {"minimum_should_match": 0, "must": [], "must_not": [], "should": []}}}}
            else:
                # Otherwise, load query from saved search
                param_query = json.loads(Search.objects.get(pk=int(search)).query)

            # Get data
            ds = Datasets().activate_datasets_by_id(self.task_params['dataset'])
            self.es_m = ds.build_manager(ES_Manager)
            self.model_name = 'model_{}'.format(self.task_obj.unique_id)
            facts = self._get_fact_values(fact_names)
            hits = self._scroll_query_response(param_query)

            # Prepare data
            X_train, y_train, X_val, y_val = self._prepare_data(hits, facts)
            # Training the model.
            show_progress.update(1)
            # Train and report validation
            model, report, confusion, plot_url = self._train_and_validate(X_train, y_train, X_val, y_val)

            self.train_summary['samples'] = len(hits)
            self.train_summary['model_type'] = 'CRF'
            report_table = self._convert_dict_to_html_table(report)
            self.train_summary['report'] = report_table
            self.train_summary['confusion_matrix'] = '<img src="{}" style="max-width: 80%">'.format(plot_url)
            show_progress.update(2)

            # Declare the job as done
            self.task_obj.result = json.dumps(self.train_summary)
            self.task_obj.update_status(Task.STATUS_COMPLETED, set_time_completed=True)

            logging.getLogger(INFO_LOGGER).info(json.dumps({
                'process': 'CREATE CRF MODEL',
                'event':   'crf_training_completed',
                'data':    {'task_id': self.task_id}
            }))

        except TaskCanceledException as e:
            # If here, task was canceled while training
            # Delete task
            self.task_obj.delete()
            logging.getLogger(INFO_LOGGER).info(json.dumps({'process': 'CREATE CLASSIFIER', 'event': 'crf_training_canceled', 'data': {'task_id': self.task_id}}), exc_info=True)
            print("--- Task canceled")

        except Exception as e:
            logging.getLogger(ERROR_LOGGER).exception(json.dumps(
                {'process': 'CREATE CLASSIFIER', 'event': 'crf_training_failed', 'data': {'task_id': self.task_id}}), exc_info=True)
            # declare the job as failed.
            self.task_obj.result = json.dumps({'error': repr(e)})
            self.task_obj.update_status(Task.STATUS_FAILED, set_time_completed=True)
        print('Done with crf task')


    def convert_and_predict(self, data, task_id):
        self.task_id = task_id
        self.task_obj = Task.objects.get(pk=self.task_id)
        self.task_type = self.task_obj.task_type
        # Recover features from model to check map
        self._load_tagger()
        self._load_facts()
        data = self._transform(data, self.facts)
        processed_data = (self._sent2features(s) for s in data)
        preds = [self.tagger.tag(x) for x in processed_data]
        return preds


    def _prepare_data(self, hits, facts):
        X_train = []
        X_val = []
        # Save all facts for later tagging
        self._save_as_pkl(facts, "meta")

        # Transform data 
        X_train, X_val = train_test_split(hits, test_size=0.1, random_state=42)
        X_train = self._transform(X_train, facts)
        X_val = self._transform(X_val, facts)

        # Create training data generators
        y_train = (self._sent2labels(s) for s in X_train)
        X_train = (self._sent2features(s) for s in X_train)
        y_val = [self._sent2labels(s) for s in X_val]
        X_val = (self._sent2features(s) for s in X_val)

        return X_train, y_train, X_val, y_val 


    def _save_as_pkl(self, var, suffix):
        # Save facts as metadata for tagging, to covert new data into training data using facts
        filename = "{}_{}".format(self.model_name, suffix)
        output_model_file = create_file_path(filename, MODELS_DIR, self.task_type)
        with open(output_model_file, "wb") as f:
            pkl.dump(var, f)


    def _transform(self, data, facts):
        # TODO instead of matching again in text, should 
        marked_docs = []
        for i, doc in enumerate(data):
            marked = []
            for word in doc.split(' '):
                if word in facts:
                    # If the word is a fact, mark it as so
                    marked.append((word, facts[word]))
                else:
                    # Add no fact, with a special tag
                    marked.append((word, self.oob_val))
            marked_docs.append(marked)
        return marked_docs


    def _word2features(self, sent, i):
        word = sent[i][0]
        # Using strings instead of bool/int to satisfy pycrfsuite
        features = [
            # Bias
            'b',
            word.lower(),
            word[-3:],
            word[-2:],
            '1' if word.isupper() else '0',
            '1' if word.istitle() else '0',
            '1' if word.isdigit() else '0']

        if i > 0:
            word1 = sent[i-1][0]
            features.extend([
                word1.lower(),
                '1' if word1.istitle() else '0',
                '1' if word1.isupper() else '0',
            ])
        else:
            features.append(self.bos_val)
            
        if i < len(sent)-1:
            word1 = sent[i+1][0]
            features.extend([
                word1.lower(),
                '1' if word1.istitle() else '0',
                '1' if word1.isupper() else '0'])
        else:
            features.append(self.eos_val)
        return features


    def _sent2features(self, sent):
        return (self._word2features(sent, i) for i in range(len(sent)))


    def _sent2labels(self, sent):
        return [label for token, label in sent]


    def _sent2tokens(self, sent):
        return (token for token, label in sent)


    def _train_and_validate(self, X_train, y_train, X_val, y_val):
        model = self._train_and_save(X_train, y_train)

        # Initialize self.tagger
        self._load_tagger()
        report, confusion, plot_url = self._validate(self.tagger, X_val, y_val)
        return model, report, confusion, plot_url


    def _load_facts(self):
        file_path = os.path.join(MODELS_DIR, self.task_type, "{}_meta".format(self.model_name))
        with open(file_path, "rb") as f:
            self.facts = pkl.load(f)


    def _load_tagger(self):
        # In pycrfsuite, you have to save the model first, then load it as a tagger
        self.model_name = 'model_{}'.format(self.task_obj.unique_id)
        file_path = os.path.join(MODELS_DIR, self.task_type, self.model_name)
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
        for i, (xseq, yseq) in enumerate(zip(X_train, y_train)):
            # Check how much memory left, stop adding more data if too little
            if i % 2500 == 0:
                if (psutil.virtual_memory().available / 1000000) < self.min_mb_available_memory:
                    print('EntityExtractorWorker:_get_memory_safe_features - Less than {} Mb of memory remaining, breaking adding more data.'.format(self.min_mb_available_memory))
                    self.train_summary["warning"] = "Trained on {} documents, because more documents don't fit into memory".format(i)
                    logging.getLogger(INFO_LOGGER).info(json.dumps({
                        'process': 'EntityExtractorWorker:_train_and_save',
                        'event':   'Less than {}Mb of memory available, stopping adding more training data. Iteration {}.'.format(self.min_mb_available_memory, i),
                        'data':    {'task_id': self.task_id}
                    }))
                    break
            trainer.append(xseq, yseq)

        trainer.set_params({
            'c1': 0.5,   # coefficient for L1 penalty
            'c2': 1e-4,  # coefficient for L2 penalty
            'max_iterations': 50,  # stop earlier
            # transitions that are possible, but not observed
            'feature.possible_transitions': True})

        output_model_path = create_file_path(self.model_name, MODELS_DIR, self.task_type)
        # Train and save
        trainer.train(output_model_path)
        return trainer


    def _classification_reports(self, y_true, y_pred):
        """
        Classification report for a list of sequences.
        It computes token-level metrics and discards self.oob_val labels.
        """
        lb = LabelBinarizer()
        y_true_combined = lb.fit_transform(list(chain.from_iterable(y_true)))
        y_pred_combined = lb.transform(list(chain.from_iterable(y_pred)))
        tagset = sorted(set(lb.classes_) - {self.oob_val})
        class_indices = {cls: idx for idx, cls in enumerate(lb.classes_)}
        # Labels accounting for the removal of self.oob_val
        class_labels = [class_indices[cls] for cls in lb.classes_]
        tagset_labels = [class_indices[cls] for cls in tagset]
        report = classification_report(
            y_true_combined,
            y_pred_combined,
            labels=tagset_labels,
            target_names=tagset,
            output_dict=True)

        # Confusion matrix
        confusion = confusion_matrix(y_pred_combined.argmax(axis=1), y_true_combined.argmax(axis=1), labels=class_labels)
        # Set the self.oob_val prediction count to 0, to balance color highlights for other classes
        confusion[class_indices[self.oob_val]][0] = 0

        cm_labels = lb.classes_
        cm_labels[class_indices[self.oob_val]] = 'None'
        # Updates the plt variable to draw a confusion matrix graph
        plt = plot_confusion_matrix(confusion, classes=cm_labels)
        plot_name = "{}_cm.svg".format(self.model_name)

        plot_path = create_file_path(plot_name, PROTECTED_MEDIA, "task_manager/", self.task_type)
        plot_url = os.path.join(URL_PREFIX, MEDIA_URL, "task_manager/", self.task_type, plot_name)
        plt.savefig(plot_path, format="svg", bbox_inches='tight')

        # Return sklearn classification_report, return report as dict
        return report, confusion, plot_url


    def _validate(self, model, X_val, y_val):
        y_pred = [model.tag(xseq) for xseq in X_val]
        report, confusion, plot_url = self._classification_reports(y_val, y_pred)
        return report, confusion, plot_url


    def _scroll_query_response(self, query):
        # Scroll the search, extract hits
        hits = []
        self.es_m.load_combined_query(query)
        response = self.es_m.scroll()
        scroll_id = response['_scroll_id']
        total_docs = response['hits']['total']
        while total_docs > 0:
            for hit in response['hits']['hits']:
                source = hit['_source']
                # Check if any of the selected facts are present in the hit fields
                fact_fields = self._get_facts_in_document(source)
                # Get the hit data of the fields where facts are present
                batch_hits = self._get_data_from_fields(source, fact_fields)

                # Add batch hits to hits
                hits += batch_hits
            response = self.es_m.scroll(scroll_id=scroll_id)
            total_docs = len(response['hits']['hits'])
            scroll_id = response['_scroll_id']
        return hits

    def _get_facts_in_document(self, source):
        fact_fields = []
        if FACT_FIELD in source:
            for fact in source[FACT_FIELD]:
                if fact['fact'] in self.task_params['facts']:
                    fact_path = fact['doc_path']
                    if fact_path not in fact_fields:
                        fact_fields.append(fact_path)
        return fact_fields


    def _get_data_from_fields(self, source, fields):
        batch_hits = []
        for field in fields:
            content = source
            for sub_f in field.split('.'):
                # Check if field is missing, in case the content is empty
                if sub_f in content:
                    content = content[sub_f]
                else:
                    content = ''
            batch_hits.append(content)
        return batch_hits


    def _get_fact_values(self, fact_names):
        aggs = {'main': {'aggs': {"facts": {"nested": {"path": "texta_facts"}, "aggs": {"fact_names": {"terms": {"field": "texta_facts.fact"}, "aggs": {"fact_values": {"terms": {"field": "texta_facts.str_val"}}}}}}}}}
        self.es_m.load_combined_query(aggs)
        response = self.es_m.search()
        response_aggs = response['aggregations']['facts']['fact_names']['buckets']

        fact_data = {}
        for fact in response_aggs:
            if fact['key'] in fact_names:
                for val in fact['fact_values']['buckets']:
                    for val_word in val["key"].split(' '):
                        fact_data[val_word] = fact["key"]
        return fact_data


    def _bad_params_result(self, msg: str):
        self.task_obj.result = json.dumps({"error": msg})
        self.task_obj.update_status(Task.STATUS_FAILED, set_time_completed=True)

    @staticmethod
    def _convert_dict_to_html_table(data_dict):
        with pd.option_context('display.precision', 3):
            df = pd.DataFrame(data=data_dict)
            df = df.fillna(' ').T
            talbe = df.to_html()
        return talbe
