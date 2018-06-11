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
                texts = [document[input_feature].decode() for document in documents if input_feature in document]
            except AttributeError:
                texts = [document[input_feature] for document in documents if input_feature in document]
            

            ## Dies with empty text!
            results = []
            tagger_descriptions = []
            
            for i,tagger in enumerate(taggers_to_apply):
                tagger_descriptions.append(tagger.description)
                result_vector = tagger.tag(texts)   
                results.append(result_vector)
            
            results_transposed = np.array(results).transpose()

            tags = []

            for tagger_ids in results_transposed:
                positive_tag_ids = np.nonzero(tagger_ids)
                positive_tags = [tagger_descriptions[positive_tag_id] for positive_tag_id in positive_tag_ids[0]]
               
                out.append(positive_tags)
                
            
        

        return classify_documentz(self._tagger_ids, documents)
