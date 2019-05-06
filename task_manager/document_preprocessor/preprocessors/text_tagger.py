from task_manager.tasks.workers.text_tagger_worker import TagModelWorker

import numpy as np
import json
from texta.settings import FACT_FIELD

class TextTaggerPreprocessor(object):
    """Preprocessor implementation for running TEXTA Text Taggers on the selected documents.
    """

    def __init__(self, feature_map={}):
        self._feature_map = feature_map

    def transform(self, documents, **kwargs):
        input_features = json.loads(kwargs['text_tagger_feature_names'])
        input_path = json.loads(kwargs['text_tagger_path'])
        tagger_ids_to_apply = [int(_id) for _id in json.loads(kwargs['text_tagger_preprocessor_models'])]
        taggers_to_apply = []

        if not input_features or not tagger_ids_to_apply:
            return {"documents":documents, "meta": {'documents_tagged': 0}}

        # Load tagger models
        for _id in tagger_ids_to_apply:
            tm = TagModelWorker()
            tm.load(_id)
            taggers_to_apply.append(tm)

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

        # Apply tags to every input feature
        results = []
        tagger_descriptions = []

        for tagger in taggers_to_apply:
            tagger_descriptions.append(tagger.description)
            result_vector = tagger.tag(text_map)
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
                    new_fact = {'fact': 'TEXTA_TAG', 'str_val': tag, 'doc_path': input_path, 'spans': json.dumps([[0, 0]])}
                    texta_facts.append(new_fact)
                documents[i][FACT_FIELD].extend(texta_facts)

        # Get total tagged documents, get np array of results
        total_positives = np.count_nonzero(results)
        return {"documents":documents, "meta": {'documents_tagged': total_positives}}
