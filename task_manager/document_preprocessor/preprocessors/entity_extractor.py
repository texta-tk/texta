from task_manager.tasks.workers.entity_extractor_worker import EntityExtractorWorker

import logging
from texta.settings import ERROR_LOGGER, FACT_FIELD
import numpy as np
import json


class EntityExtractorPreprocessor(object):
    """Preprocessor implementation for running TEXTA Entity Extractors on the selected documents.
    """

    def __init__(self, feature_map={}):
        self._feature_map = feature_map

    def transform(self, documents, **kwargs):
        try:
            input_features = json.loads(kwargs['entity_extractor_feature_names'])
            model_ids_to_apply = [int(_id) for _id in json.loads(kwargs['entity_extractor_preprocessor_models'])]
            models_to_apply = []
            facts_added = 0

            if not input_features or not model_ids_to_apply:
                return {"documents":documents, "meta": {'facts_added': facts_added}}

            # Load tagger models
            for _id in model_ids_to_apply:
                ent_ext = EntityExtractorWorker()
                models_to_apply.append(ent_ext)

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
                    text_map[field].append(decoded_text.strip())
            # Apply tags to every input feature
            for field in input_features:
                field_docs = text_map[field]
                results = []
                model_descriptions = []

                for i, model in enumerate(models_to_apply):
                    model_descriptions.append(model.description)
                    result_vector = model.convert_and_predict(field_docs, model_ids_to_apply[i])
                    results.extend(result_vector)

                new_facts = []
                for i, (doc, result_doc) in enumerate(zip(field_docs, results)):
                    new_facts, doc_num_facts = self._preds_to_doc(str(doc), result_doc, field)
                    facts_added += doc_num_facts

                    if FACT_FIELD not in documents[i]:
                        documents[i][FACT_FIELD] = new_facts
                    else:
                        documents[i][FACT_FIELD].extend(new_facts)

        except Exception as e:
            log_dict = {'task': 'APPLY PREPROCESSOR',
                       'event': 'EntityExtractorPreprocessor:transform',
                       'data': {'entity_extractor_preprocessor_models': json.loads(kwargs['entity_extractor_preprocessor_models'])}}

            logging.getLogger(ERROR_LOGGER).exception("Entity Extractor transform", extra=log_dict, exc_info=True)
            return {"documents":documents, "meta": {'facts_added': facts_added}}
        return {"documents":documents, "meta": {'facts_added': facts_added}}


    def _preds_to_doc(self, doc, result_doc, field):
        doc_num_facts = 0
        doc_spans = [0]
        new_facts = []

        for i, (word, pred) in enumerate(zip(doc.split(' '), result_doc)):
            if pred != "<TEXTA_O>":
                spans = [doc_spans[i], doc_spans[i] + len(word)]
                new_fact = {'fact': pred, 'str_val': word, 'doc_path': field, 'spans': json.dumps([spans])}
                new_facts.append(new_fact)
                doc_num_facts += 1
            # Add +1 for account for whitespace
            doc_spans.append(doc_spans[i] + len(word) + 1)
        return new_facts, doc_num_facts
