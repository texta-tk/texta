# -*- coding: utf-8 -*-

import requests
import json


class MlpProcessor(object):
    def __init__(self, mlp_url=None, enabled_features=['text', 'lang']):
        self._mlp_url = mlp_url
        self._enabled_features = set(enabled_features)

    def transform(self, documents, **kwargs):
        if not self._enabled_features:
            return documents

        if not kwargs.get('feature_map', None):
            kwargs['feature_map'] = {'text': 'text', 'lang': 'lang'}

        if not kwargs.get('input_feature', None):
            kwargs['input_feature'] = 'text'

        input_feature = kwargs['input_feature']
        feature_map = kwargs['feature_map']

        texts = [document[input_feature] for document in documents]
        data = {'texts': json.dumps(texts, ensure_ascii=False)}
        analyzation_data = requests.post(self._mlp_url, data=data).json()

        for analyzation_idx, analyzation_datum in enumerate(analyzation_data):
            analyzation_datum = analyzation_datum[0]
            for feature in analyzation_datum:
                if feature in self._enabled_features:
                    documents[analyzation_idx][feature_map[feature]] = analyzation_datum[feature]

        return documents


if __name__ == '__main__':
    mlp_processor = MlpProcessor('http://10.6.6.92/mlp/process')
    docs = [{'text': u'Mina olen väga ilus.'}, {'text': u'Little cute donkey watched as little girl ate.'}]
    mlp_processor.transform(docs, **{'feature_map': {'text': 'tekst', 'lang': 'keel'}})

    print(docs)
