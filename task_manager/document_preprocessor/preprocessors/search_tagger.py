# -*- coding: utf-8 -*-
import json

class SearchTaggerPreprocessor(object):
    """
    Tags documents based on selected search and given fact names and values.
    """

    def __init__(self):
        pass

    def transform(self, documents, **kwargs):
        """ Tags documents based on selected search and given fact names and values.
        """

        input_features = json.loads(kwargs['search_tagger_feature_names'])
        fact_name      = json.loads(kwargs['search_tagger_processor_fact_name'])
        fact_value     = json.loads(kwargs['search_tagger_processor_fact_value'])

        doc_path       = input_features[0]

        for doc in documents:
            if 'texta_facts' not in doc:
                doc['texta_facts'] = []

            new_fact = {'fact':fact_name, 'str_val':fact_value, 'spans':json.dumps([[0,0]]), 'doc_path':doc_path}
            doc['texta_facts'].append(new_fact)

        return {'documents': documents, 'meta': {}}
