
# Uses scikit-learn 0.18.1

from sklearn.feature_extraction.text import CountVectorizer
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import Normalizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.naive_bayes import BernoulliNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neighbors import RadiusNeighborsClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score
from sklearn.pipeline import Pipeline
from sklearn.externals import joblib


class ModelNull:

    def fit(self, x, y):
        # Do nothing
        return self

    def transform(self, x):
        # Do nothing
        return x


class ModelStep:

    def __init__(self, name, model, label):
        self.name = name
        self.model = model
        self.label = label

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name

    def get_step(self):
        return (self.name, self.model())


class PipelineBuilder:
    def __init__(self):
        self.extractor_list = []
        self.reductor_list = []
        self.normalizer_list = []
        self.classifier_list = []
        self.extractor_op = 0
        self.reductor_op = 0
        self.normalizer_op = 0
        self.classifier_op = 0

    def add_extractor(self, name, model, label):
        self.extractor_list.append(ModelStep(name, model, label))

    def add_reductor(self, name, model, label):
        self.reductor_list.append(ModelStep(name, model, label))

    def add_normalizer(self, name, model, label):
        self.normalizer_list.append(ModelStep(name, model, label))

    def add_classifier(self, name, model, label):
        self.classifier_list.append(ModelStep(name, model, label))

    def get_extractor_options(self):
        options = []
        for i, x in enumerate(self.extractor_list):
            options.append({'index': i, 'label': x.label})
        return options

    def get_reductor_options(self):
        options = []
        for i, x in enumerate(self.reductor_list):
            options.append({'index': i, 'label': x.label})
        return options

    def get_normalizer_options(self):
        options = []
        for i, x in enumerate(self.normalizer_list):
            options.append({'index': i, 'label': x.label})
        return options

    def get_classifier_options(self):
        options = []
        for i, x in enumerate(self.classifier_list):
            options.append({'index': i, 'label': x.label})
        return options

    def set_pipeline_options(self, extractor_op, reductor_op, normalizer_op, classifier_op):
        self.extractor_op = extractor_op
        self.reductor_op = reductor_op
        self.normalizer_op = normalizer_op
        self.classifier_op = classifier_op

    def pipeline_representation(self):
        e = self.extractor_list[self.extractor_op].name
        r = self.reductor_list[self.reductor_op].name
        n = self.normalizer_list[self.normalizer_op].name
        c = self.classifier_list[self.classifier_op].name
        rep = "{0} -> {1} -> {2} -> {3}".format(e, r, n, c)
        return rep

    def build(self):
        steps = []
        steps.append(self.extractor_list[self.extractor_op].get_step())
        steps.append(self.reductor_list[self.reductor_op].get_step())
        steps.append(self.normalizer_list[self.normalizer_op].get_step())
        steps.append(self.classifier_list[self.classifier_op].get_step())
        pipe = Pipeline(steps)
        return pipe


def get_pipeline_builder():

    pipe_builder = PipelineBuilder()

    # Feature Extraction
    pipe_builder.add_extractor('CountVectorizer', CountVectorizer, 'Count Vectorizer')
    pipe_builder.add_extractor('HashingVectorizer', HashingVectorizer, 'Hashing Vectorizer')
    pipe_builder.add_extractor('TfidfVectorizer', TfidfVectorizer, 'TfIdf Vectorizer')

    # Dimension Reduction
    pipe_builder.add_reductor('No_Reduction', ModelNull, 'None')
    pipe_builder.add_reductor('TruncatedSVD', TruncatedSVD, 'Truncated SVD')

    # Normalization
    pipe_builder.add_normalizer('No_Normalization', ModelNull, 'None')
    pipe_builder.add_normalizer('Normalizer', Normalizer, 'Normalizer')

    # Classification Models
    pipe_builder.add_classifier('MultinomialNB', MultinomialNB, 'Multinomial Naive Bayes')
    pipe_builder.add_classifier('BernoulliNB', BernoulliNB, 'Bernoulli Naive Bayes')
    pipe_builder.add_classifier('KNeighborsClassifier', KNeighborsClassifier, 'K-Neighbors')
    pipe_builder.add_classifier('RadiusNeighborsClassifier', RadiusNeighborsClassifier, 'Radius Neighbors')

    return pipe_builder


def train_model_with_cv(model, X, y):
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.20)
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    score = f1_score(y_test, y_pred, average='micro')
    return model, score


def save_model(model, file_name):
    joblib.dump(model, file_name)


def load_model(file_name):
    model = joblib.load(file_name)
    return model

