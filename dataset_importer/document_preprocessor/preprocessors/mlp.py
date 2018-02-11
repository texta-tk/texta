# -*- coding: utf-8 -*-

import requests
import json


class MlpProcessor(object):
    def __init__(self, mlp_url=None, enabled_features=['text', 'lang', 'texta_facts']):
        self._mlp_url = mlp_url
        self._enabled_features = set(enabled_features)

    def transform(self, documents, **kwargs):
        if not self._enabled_features:
            return documents

        if not kwargs.get('mlp_preprocessor_input_features', None):
            kwargs['mlp_preprocessor_input_features'] = '["text"]'

        input_features = json.loads(kwargs['mlp_preprocessor_input_features'])

        for input_feature in input_features:
            texts = [document[input_feature] for document in documents]
            data = {'texts': json.dumps(texts, ensure_ascii=False)}
            analyzation_data = requests.post(self._mlp_url, data=data).json()

            for analyzation_idx, analyzation_datum in enumerate(analyzation_data):
                analyzation_datum = analyzation_datum[0]
                
                documents[analyzation_idx]['mlp_' + input_feature] = analyzation_datum['text']
                documents[analyzation_idx]['mlp_' + input_feature]['lang'] = analyzation_datum['lang']

                if 'texta_facts' not in documents[analyzation_idx]:
                    documents[analyzation_idx]['texta_facts'] = []

                documents[analyzation_idx]['texta_facts'].extend(analyzation_datum['texta_facts'])

        return documents


if __name__ == '__main__':
    mlp_processor = MlpProcessor('http://10.6.6.92/mlp/process')
    docs = [{'text': u'Mina olen väga ilus.'}, {'text': u'Little cute donkey watched as little girl ate.'}]
    mlp_processor.transform(docs, **{'feature_map': {'text': 'tekst', 'lang': 'keel'}})

    print(docs)
