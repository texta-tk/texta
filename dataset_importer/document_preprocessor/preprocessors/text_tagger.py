from task_manager.tag_manager.tag_manager import TaggingModel, tag_texts
from task_manager.models import Task

import numpy as np
import json

enabled_tagger_ids = [tagger.pk for tagger in Task.objects.filter(task_type='train_tagger').filter(status='completed')]
enabled_taggers = {}

# Load Tagger models
for _id in enabled_tagger_ids:
    tm = TaggingModel()
    tm.load(_id)
    enabled_taggers[_id] = tm

class TextTaggerPreprocessor(object):
    """Preprocessor implementation for running TEXTA Text Taggers on the selected documents.
    """

    def __init__(self, feature_map={}):
        self._feature_map = feature_map

    def transform(self, documents, **kwargs):
        input_features = json.loads(kwargs['text_tagger_preprocessor_input_features'])
        tagger_ids_to_apply = [int(_id) for _id in json.loads(kwargs['text_tagger_preprocessor_taggers'])]
        taggers_to_apply = [enabled_taggers[_id] for _id in tagger_ids_to_apply if _id in enabled_taggers]
        
        for input_feature in input_features:
            try:
                texts = [document[input_feature].strip().decode() for document in documents if input_feature in document]
            except AttributeError:
                texts = [document[input_feature].strip() for document in documents if input_feature in document]
            
            ## Dies with empty text!
            results = []
            tagger_descriptions = []
            
            for tagger in taggers_to_apply:
                tagger_descriptions.append(tagger.description)
                result_vector = tagger.tag(texts)
                results.append(result_vector)
            
            results_transposed = np.array(results).transpose()

            for i,tagger_ids in enumerate(results_transposed):
                positive_tag_ids = np.nonzero(tagger_ids)
                positive_tags = [tagger_descriptions[positive_tag_id] for positive_tag_id in positive_tag_ids[0]]
                texta_facts = []
                
                if positive_tags:               
                    if 'texta_facts' not in documents[i]:
                        documents[i]['texta_facts'] = []               
                    for tag in positive_tags:
                        new_fact = {'fact': 'TEXTA_TAG', 'str_val': tag, 'doc_path': input_feature, 'spans': json.dumps([[0,len(texts[i])]])}
                        texta_facts.append(new_fact)
                
                    documents[i]['texta_facts'].extend(texta_facts)        

        return documents
