from task_manager.tasks.workers.entity_extractor_worker import EntityExtractorWorker

import numpy as np
import json


class EntityExtractorPreprocessor(object):
    """Preprocessor implementation for running TEXTA Entity Extractors on the selected documents.
    """

    def __init__(self, feature_map={}):
        self._feature_map = feature_map

    def transform(self, documents, **kwargs):
        try:
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
                field_docs = text_map[field]
                results = []
                model_descriptions = []

                for i, model in enumerate(models_to_apply):
                    # import pdb;pdb.set_trace()
                    model_descriptions.append(model.description)
                    result_vector = model.convert_and_predict(field_docs, model_ids_to_apply[i])
                    results.extend(result_vector)

                import pdb;pdb.set_trace()
                new_facts = []
                facts_added = 0
                for i, (doc, result_doc) in enumerate(zip(field_docs, results)):
                    new_facts, doc_num_facts = self._preds_to_doc(str(doc), result_doc, field)
                    facts_added += doc_num_facts

                    if 'texta_facts' not in documents[i]:
                        documents[i]['texta_facts'] = new_facts
                    else:
                        documents[i]['texta_facts'].extend(new_facts)
                
                print('loop')
                import pdb;pdb.set_trace()
                print('done')
                # if 'texta_facts' not in documents[i]:
                    # documents[i]['texta_facts'] = []
                    # new_fact = {'fact': 'TEXTA_TAG', 'str_val': tag, 'doc_path': field, 'spans': json.dumps("""TODO""")}
                    # texta_facts.append(new_fact)
                # else:
                    # documents[i]['texta_facts'].extend(texta_facts)

                # Get total tagged documents, get np array of results
        except Exception as e:
            print(e)
            import pdb;pdb.set_trace()

        return {"documents":documents, "meta": {'facts_added': facts_added}}


    def _preds_to_doc(self, doc, result_doc, field):
        doc_num_facts = 0
        doc_spans = [0]
        new_facts = []
        try:
            for i, (word, pred) in enumerate(zip(doc.split(' '), result_doc)):
                if pred != "<TEXTA_O>":
                    spans = [doc_spans[i], doc_spans[i] + len(word)]
                    new_fact = {'fact': pred, 'str_val': word, 'doc_path': field, 'spans': json.dumps([spans])}
                    new_facts.append(new_fact)
                    doc_num_facts += 1;
                doc_spans.append(len(word))
        except Exception as e:
            print(e)
            import pdb;pdb.set_trace()

        return new_facts, doc_num_facts


    def _pred_to_fact(self, pred, ind, doc):
        pass
