import json
import pickle
import scipy
import scipy.stats
from sklearn.cross_validation import cross_val_score
from sklearn.grid_search import RandomizedSearchCV
from sklearn.metrics import make_scorer
from sklearn.model_selection import train_test_split
import sklearn_crfsuite
from sklearn_crfsuite import metrics
from sklearn_crfsuite import scorers

class EntityExtractorWorker():
    def __init__(self, field, data, limiter=None):
        self.field = field
        self.data = data[:limiter] if limiter else data


    def process_and_train(self):
        X_train, y_train, X_val, y_val = self._prepare_data()
        model, f1_score, report = self._train_and_validate(X_train, y_train, X_val, y_val)
        return model, f1_score, report


    def _train_and_validate(self, X_train, y_train, X_val, y_val):
        model = self._train(X_train, y_train)
        f1_score, report = self._validate(model, X_val, y_val)
        return model, f1_score, report


    def _prepare_data(self):
        X_train, X_val = train_test_split(self.data, test_size=0.1, random_state=42)
        facts_train = self._extract_facts(X_train)
        facts_val = self._extract_facts(X_val)
        X_train = self._transform(X_train, facts_train)
        X_val = self._transform(X_val, facts_val)

        y_train = [self._sent2labels(s) for s in X_train]
        X_train = [self._sent2features(s) for s in X_train]
        y_val = [self._sent2labels(s) for s in X_val]
        X_val = [self._sent2features(s) for s in X_val]
        return X_train, y_train, X_val, y_val 


    def _extract_facts(self, data):
        facts = {}
        for doc in data:
            if "texta_facts" in doc["_source"]:
                for fact in doc["_source"]["texta_facts"]:
                    if fact["str_val"] not in facts:
                        facts[fact["str_val"]] = fact["fact"]
        return facts


    def _transform(self, data, facts):
        marked_docs = []
        for i, doc in enumerate(data):
            marked = []
            if 'texta_facts' in doc['_source']:
                for word in doc['_source']['field_value_raw_mlp']['text'].split(' '):
                    if word in facts:
                        marked.append((word, facts[word]))
                    else:
                        marked.append((word, 'O'))
                marked_docs.append(marked)

            if i % 5000 == 0:
                print(i)

        return marked_docs


    def _word2features(self, sent, i, facts=None):
        word = sent[i][0]

        features = {
            'bias': 1.0,
            'word.lower()': word.lower(),
            'word[-3:]': word[-3:],
            'word[-2:]': word[-2:],
            'word.isupper()': word.isupper(),
            'word.istitle()': word.istitle(),
            'word.isdigit()': word.isdigit(),
    #         'word.in_facts': word in all_facts,
    #         'word.fact_name': all_facts[word] if facts and word in all_facts else 'none',
        }
        if i > 0:
            word1 = sent[i-1][0]
            features.update({
                '-1:word.lower()': word1.lower(),
                '-1:word.istitle()': word1.istitle(),
                '-1:word.isupper()': word1.isupper(),
    #             '-1:word.in_facts': word1 in all_facts,
    #             '-1:word.fact_name': all_facts[word1] if facts and word1 in all_facts else 'none',
            })
        else:
            features['BOS'] = True
            
        if i < len(sent)-1:
            word1 = sent[i+1][0]
            features.update({
                '+1:word.lower()': word1.lower(),
                '+1:word.istitle()': word1.istitle(),
                '+1:word.isupper()': word1.isupper(),
    #             '+1:word.in_facts': word1 in all_facts,
    #             '+1:word.fact_name': all_facts[word1] if facts and word1 in all_facts else 'none',
            })
        else:
            features['EOS'] = True
                    
        return features


    def _sent2features(self, sent, facts=None):
        return [self._word2features(sent, i, facts) for i in range(len(sent))]


    def _sent2labels(self, sent):
        return [label for token, label in sent]


    def _sent2tokens(self, sent):
        return [token for token, label in sent]


    def _train(self, X_train, y_train):
        crf = sklearn_crfsuite.CRF(
            algorithm='lbfgs', 
            c1=0.1, 
            c2=0.1, 
            max_iterations=100, 
            all_possible_transitions=True,
            verbose=True
        )
        crf.fit(X_train, y_train)
        return crf


    def _validate(self, model, X_val, y_val):
        labels = list(model.classes_)
        labels.remove('O')

        y_pred = model.predict(X_val)
        f1_score = metrics.flat_f1_score(y_val, y_pred, average='weighted', labels=labels)

        sorted_labels = sorted(labels, key=lambda name: (name[1:], name[0]))
        report = metrics.flat_classification_report(y_val, y_pred, labels=sorted_labels, digits=3)
        return f1_score, report


if __name__ == "__main__":
    field = 'field_value_raw_mlp.text'
    print('Loading data...')
    data = []
    with open("/home/ulm/Documents/machinelearning/DATA/delfi_crf/scoro.json") as f:
        for line in f.readlines():
            data.append(json.loads(line))
    print('Initializing...')
    limiter = 100000
    EntityExtractor = EntityExtractorWorker(field, data, limiter)
    print('Training...')
    model, f1_score, report = EntityExtractor.process_and_train()
    print('Done!')
    print(f1_score)
    print(report)

    import pdb;pdb.set_trace()
