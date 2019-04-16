from typing import List, Dict

# Data imports
import csv
import json
import numpy as np
from keras.preprocessing.text import Tokenizer, text_to_word_sequence
from keras.preprocessing.sequence import pad_sequences

# Task imports
from task_manager.tasks.workers.neuroclassifier.neuroclassifier_worker import NeuroClassifierWorker
from texta.settings import FACT_FIELD

class NeuroClassifierPreprocessor():
    '''Classify documents with a trained NeuroClassifier model'''
    def __init__(self, feature_map={}):
        self.feature_map = feature_map

    def transform(self, documents, **kwargs):
        input_features, input_path, ids_to_apply = self._set_up_params(**kwargs)

        if not input_features or not ids_to_apply:
            return {"documents":documents, "meta": {"documents_tagged": 0}}

        models = self._load_models(ids_to_apply)
        text_map = self._generate_text_map(documents, input_features)
        result = self._tag_documents(models, text_map, ids_to_apply, documents, input_path)
        return result
    

    def _set_up_params(self, **kwargs):
        input_features = json.loads(kwargs['neuroclassifier_feature_names'])
        input_path = json.loads(kwargs['neuroclassifier_path'])
        ids_to_apply = [int(_id) for _id in json.loads(kwargs['neuroclassifier_preprocessor_models'])]

        return input_features, input_path, ids_to_apply


    def _load_models(self, ids_to_apply):
        models = []
        # Load neuroclassifier models
        for _id in ids_to_apply:
            worker = NeuroClassifierWorker()
            worker.load(_id)
            # Append worker for predicting within the worker
            models.append(worker)

        return models
    

    def _generate_text_map(self, documents, input_features):
        # Starts text map
        text_map = {}
        for field in input_features:
            text_map[field] = []

        # Prepare text map with docs
        for document in documents:
            # Extract text
            for field in input_features:
                decoded_text = document
                for k in field.split('.'):
                    if k in decoded_text:
                        decoded_text = decoded_text[k]
                    else:
                        decoded_text = ''
                        break
                
                # sanity check to filter out None values
                if not decoded_text:
                    decoded_text = ''

                try:
                    text_map[field].append(decoded_text.strip().decode())
                except AttributeError:
                    text_map[field].append(decoded_text.strip())
        return text_map


    def _tag_documents(self, models, text_map, model_ids, documents, input_path):
        # Apply tags to every input feature
        results = []
        tagger_descriptions = []

        for tagger in models:
            tagger_descriptions.append(tagger.task_obj.description)
            for field in text_map:
                result_vector = np.squeeze(tagger.convert_and_predict(text_map[field]))
                results.append(result_vector)
        results_transposed = np.array(results).transpose()

        for i, tagger_ids in enumerate(results_transposed):
            positive_tag_ids = np.nonzero(tagger_ids)
            positive_tags = [tagger_descriptions[positive_tag_id] for positive_tag_id in positive_tag_ids[0]]
            texta_facts = []
            if positive_tags:
                if FACT_FIELD not in documents[i]:
                    documents[i][FACT_FIELD] = []
                for tag in positive_tags:
                    new_fact = {'fact': 'TEXTA_TAG', 'str_val': tag, 'doc_path': input_path, 'spans': json.dumps([0, 0])}
                    texta_facts.append(new_fact)
                documents[i][FACT_FIELD].extend(texta_facts)

        # Get total tagged documents, get np array of results
        total_positives = np.count_nonzero(results)
        return {"documents": documents, "meta": {"documents_tagged": total_positives}}
