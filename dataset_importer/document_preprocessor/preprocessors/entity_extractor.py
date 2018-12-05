from task_manager.tasks.workers.entity_extractor_worker import EntityExtractorWorker

import numpy as np
import json


class EntityExtractorPreprocessor(object):
    """Preprocessor implementation for running TEXTA Entity Extractors on the selected documents.
    """

    def __init__(self, feature_map={}):
        self._feature_map = feature_map

    def transform(self, documents, **kwargs):
        input_features = json.loads(kwargs['entity_extractor_preprocessor_feature_names'])
        model_ids_to_apply = [int(_id) for _id in json.loads(kwargs['entity_extractor_preprocessor_extractors'])]
        models_to_apply = []
        if not input_features:
            return documents

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
                try:
                    text_map[field].append(decoded_text.strip().decode())
                except AttributeError:
                    text_map[field].append(decoded_text.strip())
        # Apply tags to every input feature
        for field in input_features:
            results = []
            model_descriptions = []

            for i, model in enumerate(models_to_apply):
                import pdb;pdb.set_trace()
                model_descriptions.append(model.description)
                result_vector = model.convert_and_predict(text_map[field], model.facts, model_ids_to_apply[i])
                results.append(result_vector)
            # results_transposed = np.array(results).transpose()
            import pdb;pdb.set_trace()
            for i, result in enumerate(results):
                # positive_tag_ids = np.nonzero(tagger_ids)
                # positive_tags = [tagger_descriptions[positive_tag_id] for positive_tag_id in positive_tag_ids[0]]
                texta_facts = []
                # TODO GET VALUES THAT HAVE SOMETHING MARKED AND APPLY THEM
                if positive_tags:
                    if 'texta_facts' not in documents[i]:
                        documents[i]['texta_facts'] = []
                    for tag in positive_tags:
                        new_fact = {'fact': 'TEXTA_TAG', 'str_val': tag, 'doc_path': field, 'spans': json.dumps("""TODO""")}
                        texta_facts.append(new_fact)
                    documents[i]['texta_facts'].extend(texta_facts)

            # Get total tagged documents, get np array of results
            total_positives = np.count_nonzero(results)

        return {"documents":documents, "meta": {'documents_tagged': total_positives}}
