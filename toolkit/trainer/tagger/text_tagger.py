from toolkit.trainer.tagger.pipeline import get_pipeline_builder
from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score
from sklearn.externals import joblib
from sklearn.metrics import confusion_matrix
from sklearn.metrics import precision_score
from sklearn.metrics import recall_score
from sklearn.model_selection import GridSearchCV
import pandas as pd
import json

from toolkit.settings import NUM_WORKERS
from toolkit.trainer.models import Tagger


class TextTagger:

    def __init__(self, tagger_id, field_list=[], classifier=0, vectorizer=0, workers=NUM_WORKERS):
        self.model = None
        self.statistics = None
        self.tagger_id = int(tagger_id)
        self.workers = workers
        self.field_list = field_list
        self.pipe_builder = get_pipeline_builder()
        self.pipe_builder.set_pipeline_options(vectorizer, classifier)
        self.c_pipe, self.c_params = self.pipe_builder.build(fields=self.field_list)


    def _create_data_map(self, data):
        data_map = {}
        for document in data:
            for field in self.field_list:
                if field not in data_map:
                    data_map[field] = []
                if field in document:
                    data_map[field].append(document[field])
                else:
                    data_map[field].append('')
        return data_map


    def train(self, positive_samples, negative_samples):
        positive_samples_map = self._create_data_map(positive_samples)
        negative_samples_map = self._create_data_map(negative_samples)

        # Build X feature map
        data_sample_x_map = {}
        for field in self.field_list:
            data_sample_x_map[field] = positive_samples_map[field] + negative_samples_map[field]
        
        # Build target (positive + negative samples) for binary classifier
        data_sample_y = [1] * len(positive_samples) + [0] * len(negative_samples)

        X_train = {}
        X_test = {}

        for field in self.field_list:
            X_train[field], X_test[field], y_train, y_test = train_test_split(data_sample_x_map[field], data_sample_y, test_size=0.20, random_state=42)

        df_train = pd.DataFrame(X_train)
        df_test = pd.DataFrame(X_test)

        # Use Train data to parameter selection in a Grid Search
        gs_clf = GridSearchCV(self.c_pipe, self.c_params, n_jobs=self.workers, cv=5, verbose=1)
        gs_clf = gs_clf.fit(df_train, y_train)
        model = gs_clf.best_estimator_
        # Use best model and test data for final evaluation
        y_pred = model.predict(df_test)
        # Report
        f1 = f1_score(y_test, y_pred, average='micro')
        confusion = confusion_matrix(y_test, y_pred)
        precision = precision_score(y_test, y_pred)
        recall = recall_score(y_test, y_pred)

        statistics = {
            'f1_score':         round(f1, 3),
            'confusion_matrix': confusion.tolist(),
            'precision':        round(precision, 3),
            'recall':           round(recall, 3)
        }

        self.model = model
        self.statistics = statistics
        return model
    

    def save(self, file_path):
        joblib.dump(self.model, file_path)
        return True
    

    def load(self):
        tagger_object = Tagger.objects.get(pk=self.tagger_id)
        tagger_path = json.loads(tagger_object.location)['tagger']
        self.model = joblib.load(tagger_path)
        self.statistics = json.loads(tagger_object.statistics)
        return True
