from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.feature_selection import SelectFromModel, SelectKBest, mutual_info_classif
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import Normalizer
from sklearn.svm import SVC, LinearSVC
from sklearn.naive_bayes import BernoulliNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neighbors import RadiusNeighborsClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.pipeline import FeatureUnion


class ModelNull(BaseEstimator):

    def fit(self, x, y):
        # Do nothing
        return self

    def transform(self, x):
        # Do nothing
        return x


class ModelStep:

    def __init__(self, name, model, label, params, estimator=None):
        self.name = name
        self.model = model
        self.label = label
        self.params = params
        self.estimator = estimator

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name

    def get_step(self):
        if self.estimator:
            return (self.name, self.model(self.estimator))
        else:
            return (self.name, self.model())

    def get_param(self):
        param_dict = {}
        for k in self.params:
            p_name = '{0}__{1}'.format(self.name, k)
            p_value = self.params[k]
            param_dict[p_name] = p_value
        return param_dict


class ItemSelector(BaseEstimator, TransformerMixin):
    """For data grouped by feature, select subset of data at a provided key.
    The data is expected to be stored in a 2D data structure, where the first
    index is over features and the second is over samples.  i.e.
    >> len(data[key]) == n_samples
    Please note that this is the opposite convention to scikit-learn feature
    matrixes (where the first index corresponds to sample).
    ItemSelector only requires that the collection implement getitem
    (data[key]).  Examples include: a dict of lists, 2D numpy array, Pandas
    DataFrame, numpy record array, etc.
    >> data = {'a': [1, 5, 2, 5, 2, 8],
               'b': [9, 4, 1, 4, 1, 3]}
    >> ds = ItemSelector(key='a')
    >> data['a'] == ds.transform(data)
    ItemSelector is not designed to handle data grouped by sample.  (e.g. a
    list of dicts).  If your data is structured this way, consider a
    transformer along the lines of `sklearn.feature_extraction.DictVectorizer`.
    Parameters
    ----------
    key : hashable, required
        The key corresponding to the desired value in a mappable.
    Reference: http://scikit-learn.org/0.19/auto_examples/hetero_feature_union.html
    """
    def __init__(self, key):
        self.key = key

    def fit(self, x, y=None):
        return self

    def transform(self, data_dict):
        return data_dict[self.key]


class PipelineBuilder:

    def __init__(self):
        self.extractor_dict = {}
        self.classifier_dict = {}
        self.feature_selector_dict = {}
        self.extractor_op = None
        self.classifier_op = None
        self.feature_selector_op = None

    def add_extractor(self, name, model, label, params):
        self.extractor_dict[label] = ModelStep(name, model, label, params)

    def add_classifier(self, name, model, label, params):
        self.classifier_dict[label] = ModelStep(name, model, label, params)

    def add_feature_selector(self, name, model, label, params, estimator=None):
        self.feature_selector_dict[label] = ModelStep(name, model, label, params, estimator=estimator)

    def get_extractor_options(self):
        return list(self.extractor_dict.keys())

    def get_classifier_options(self):
        return list(self.classifier_dict.keys())

    def get_feature_selector_options(self):
        return list(self.feature_selector_dict.keys())

    def set_pipeline_options(self, extractor_op, classifier_op, feature_selector_op):
        self.extractor_op = extractor_op
        self.classifier_op = classifier_op
        self.feature_selector_op = feature_selector_op

    def pipeline_representation(self):
        e = self.extractor_dict[self.extractor_op]
        c = self.classifier_dict[self.classifier_op]
        s = self.feature_selector_dict[self.classifier_op]
        rep = "{0} | {1} | {2}".format(e, c, s)
        return rep

    def build(self, fields):
        """ Build model Pipeline and Grid Search params
        """
        params = {}
        # Field transform pipeline per field + params
        transformer_list = []

        for field in fields:
            pipe_key = 'pipe_{}'.format(field)
            steps = []    
            steps.append(tuple(['selector', ItemSelector(key=field)]))
            steps.append(self.extractor_dict[self.extractor_op].get_step())
            transformer_list.append(tuple([pipe_key, Pipeline(steps)]))
            # Nest params inside the union field - Extractor
            p_dict = self.extractor_dict[self.extractor_op].get_param()
            for k in p_dict:
                new_k = '{}__{}__{}'.format('union', pipe_key, k)
                params[new_k] = p_dict[k]

        # Classifier pipeline + params
        steps = []
        steps.append(tuple(['union', FeatureUnion(transformer_list=transformer_list)]))
        
        # Feature selector
        steps.append(self.feature_selector_dict[self.feature_selector_op].get_step())

        steps.append(self.classifier_dict[self.classifier_op].get_step())
        pipe = Pipeline(steps)
        params.update(self.classifier_dict[self.classifier_op].get_param())

        return pipe, params


def get_pipeline_builder():
    pipe_builder = PipelineBuilder()
    ### params are used grid search to find optimal choices

    # Feature Extraction
    analyzer_params = ['word', 'char_wb', 'char']
    ngram_params = [(1, 1), (1, 2), (1, 3)]

    params = {'ngram_range': ngram_params, 'analyzer': analyzer_params}
    pipe_builder.add_extractor('vectorizer', HashingVectorizer, 'Hashing Vectorizer', params)

    params = {'ngram_range': ngram_params, 'min_df': [5, 10]}
    pipe_builder.add_extractor('vectorizer', CountVectorizer, 'Count Vectorizer', params)

    params = {'ngram_range': ngram_params, 'min_df': [5, 10]}
    pipe_builder.add_extractor('vectorizer', TfidfVectorizer, 'TfIdf Vectorizer', params)

    # Classification Models
    params = {'solver': ['lbfgs'], 'C': [0.1, 1.0, 10, 100], 'penalty': ['l2']}
    pipe_builder.add_classifier('classifier', LogisticRegression, 'Logistic Regression', params)

    params = {'probability': [True], 'kernel': ['linear']}
    pipe_builder.add_classifier('classifier', SVC, 'LinearSVC', params)

    # Feature selectors
    params = {}
    pipe_builder.add_feature_selector('feature_selector', SelectFromModel, 'SVM Feature Selector', params, estimator=LinearSVC(penalty='l1', dual=False))

    return pipe_builder
    