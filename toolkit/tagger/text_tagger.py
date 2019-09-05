import warnings
from sklearn.exceptions import DataConversionWarning
warnings.filterwarnings(action='ignore', category=DataConversionWarning)

from toolkit.tagger.pipeline import get_pipeline_builder
from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score
from sklearn.metrics import confusion_matrix, precision_score, recall_score, roc_curve, auc
from sklearn.model_selection import GridSearchCV
import pandas as pd
import numpy as np
import joblib
import json

from toolkit.settings import NUM_WORKERS
from toolkit.tagger.models import Tagger


class TextTagger:

    def __init__(self, tagger_id, workers=NUM_WORKERS, text_processor=None):
        self.model = None
        self.statistics = None
        self.tagger_id = int(tagger_id)
        self.workers = workers
        self.description = None
        self.text_processor = None


    def _create_data_map(self, data, field_list):
        data_map = {field: [] for field in field_list}

        for document in data:
            for field in field_list:
                if field in document:
                    data_map[field].append(document[field])
                else:
                    data_map[field].append('')
        return data_map


    def add_text_processor(self, text_processor):
        self.text_processor = text_processor


    def train(self, positive_samples, negative_samples, field_list=[], classifier='Logistic Regression', vectorizer='Hashing Vectorizer', feature_selector='SVM Feature Selector'):
        positive_samples_map = self._create_data_map(positive_samples, field_list)
        negative_samples_map = self._create_data_map(negative_samples, field_list)

        pipe_builder = get_pipeline_builder()
        pipe_builder.set_pipeline_options(vectorizer, classifier, feature_selector)
        c_pipe, c_params = pipe_builder.build(fields=field_list)

        # Build X feature map
        data_sample_x_map = {}
        for field in field_list:
            data_sample_x_map[field] = positive_samples_map[field] + negative_samples_map[field]
        
        # Build target (positive + negative samples) for binary classifier
        data_sample_y = [1] * len(positive_samples) + [0] * len(negative_samples)

        X_train = {}
        X_test = {}

        for field in field_list:
            X_train[field], X_test[field], y_train, y_test = train_test_split(data_sample_x_map[field], data_sample_y, test_size=0.20, random_state=42)

        df_train = pd.DataFrame(X_train)
        df_test = pd.DataFrame(X_test)

        # Use Train data to parameter selection in a Grid Search
        gs_clf = GridSearchCV(c_pipe, c_params, n_jobs=self.workers, cv=5, verbose=False)
        gs_clf = gs_clf.fit(df_train, y_train)
        model = gs_clf.best_estimator_
        self.model = model
        # Use best model and test data for final evaluation
        y_pred = model.predict(df_test)
        # Report
        f1 = f1_score(y_test, y_pred, average='micro')
        confusion = confusion_matrix(y_test, y_pred)
        precision = precision_score(y_test, y_pred)
        recall = recall_score(y_test, y_pred)

        y_scores = model.decision_function(df_test)
        fpr, tpr, _ = roc_curve(y_test, y_scores)
        roc_auc = auc(fpr, tpr)

        feature_coefs = self.get_feature_coefs()
        num_features = len(feature_coefs)

        statistics = {
            'f1_score':             f1,
            'confusion_matrix':     confusion,
            'precision':            precision,
            'recall':               recall,
            'true_positive_rate':   tpr,
            'false_positive_rate':  fpr,
            'area_under_curve':     roc_auc,
            'num_features':         num_features,
            'feature_coefs':        feature_coefs
        }       

        self.statistics = statistics
        return model
    

    def get_feature_coefs(self):
        """
        Return feature coefficients for a given model.
        """
        coef_matrix = self.model.named_steps['classifier'].coef_
        # transform matrix if needed
        if type(coef_matrix) == np.ndarray:
            feature_coefs = coef_matrix[0]
        else:
            feature_coefs = coef_matrix.todense().tolist()[0]
        return feature_coefs


    def get_feature_names(self):
        """
        Returns feature names for a given model.
        """
        return self.model.named_steps['union'].transformer_list[0][1].named_steps['vectorizer'].get_feature_names()


    def get_supports(self):
        """
        Returns supports for a given model.
        """
        return self.model.named_steps['feature_selector'].get_support()


    def save(self, file_path):
        joblib.dump(self.model, file_path)
        return True
    

    def load(self):
        tagger_object = Tagger.objects.get(pk=self.tagger_id)
        tagger_path = json.loads(tagger_object.location)['tagger']
        self.model = joblib.load(tagger_path)
        self.description = tagger_object.description
        return True


    def tag_text(self, text):
        """
        Predicts on raw text
        :param text: input text as string
        :return: binary decision (1 is positive)
        """
        union_features = [x[0] for x in self.model.named_steps['union'].transformer_list if x[0].startswith('pipe_')]
        field_features = [x[5:] for x in union_features]

        # process text if asked
        if self.text_processor:
            text = self.text_processor.process(text)[0]

        # generate text map for dataframe
        text_map = {feature_name:[text] for feature_name in field_features}
        df_text = pd.DataFrame(text_map)

        return self.model.predict(df_text)[0], max(self.model.predict_proba(df_text)[0])



    def tag_doc(self, doc):
        """
        Predicts on json document
        :param text: input doc as json string
        :return: binary decision (1 is positive)
        """
        union_features = [x[0] for x in self.model.named_steps['union'].transformer_list if x[0].startswith('pipe_')]
        field_features = [x[5:] for x in union_features]
        
        # generate text map for dataframe
        text_map = {}
        for field in field_features:
            if field in doc:
                # process text if asked
                if self.text_processor:
                    doc_field = self.text_processor.process(doc[field])[0]
                else:
                    doc_field = doc[field]
                text_map[field] = [doc_field]
            else:
                text_map[field] = [""]

        df_text = pd.DataFrame(text_map)
        return self.model.predict(df_text)[0], max(self.model.predict_proba(df_text)[0])
