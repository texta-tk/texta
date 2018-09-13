from task_manager.tasks.workers.tag_model_worker import TagModelWorker

import numpy as np
import json


class TextTaggerPreprocessor(object):
    """Preprocessor implementation for running TEXTA Text Taggers on the selected documents.
    """

    def __init__(self, feature_map={}):
        self._feature_map = feature_map

    def transform(self, documents, **kwargs):
        input_features = json.loads(kwargs['text_tagger_preprocessor_feature_names'])
        tagger_ids_to_apply = [int(_id) for _id in json.loads(kwargs['text_tagger_preprocessor_taggers'])]
        taggers_to_apply = []

        if not kwargs.get('text_tagger_preprocessor_feature_names', None):
            return documents

        # Load tagger models
        for _id in tagger_ids_to_apply:
            tm = TagModelWorker()
            tm.load(_id)
            taggers_to_apply.append(tm)

        for input_feature in input_features:
            texts = []

            for document in documents:
                # Take into account nested fields encoded as: 'field.sub_field'
                decoded_text = document
                for k in input_feature.split('.'):
                    # Field might be empty and not included in document
                    if k in decoded_text:
                        decoded_text = decoded_text[k]
                    else:
                        decoded_text = ''
                        break

                try:
                    decoded_text.strip().decode()
                except AttributeError:
                    decoded_text.strip()

                texts.append(decoded_text)

            if not texts:
                return documents

            # TODO: this comment looks important
            ## Dies with empty text!
            results = []
            tagger_descriptions = []

            for tagger in taggers_to_apply:
                tagger_descriptions.append(tagger.description)
                result_vector = tagger.tag(texts)
                results.append(result_vector)

            results_transposed = np.array(results).transpose()

            for i, tagger_ids in enumerate(results_transposed):
                positive_tag_ids = np.nonzero(tagger_ids)
                positive_tags = [tagger_descriptions[positive_tag_id] for positive_tag_id in positive_tag_ids[0]]
                texta_facts = []

                if positive_tags:
                    if 'texta_facts' not in documents[i]:
                        documents[i]['texta_facts'] = []
                    for tag in positive_tags:
                        new_fact = {'fact': 'TEXTA_TAG', 'str_val': tag, 'doc_path': input_feature, 'spans': json.dumps([[0, len(texts[i])]])}
                        texta_facts.append(new_fact)

                    documents[i]['texta_facts'].extend(texta_facts)

            # Get total tagged documents, get np array of results
            total_positives = np.count_nonzero(results)

        return {"documents": documents, "meta": {'total_positives': total_positives}}
