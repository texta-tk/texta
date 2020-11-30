import pickle
import re
from collections import defaultdict
from typing import List

import numpy as np
from gensim import corpora, models, utils
from gensim.matutils import corpus2csc
from gensim.parsing.preprocessing import preprocess_string, strip_short, strip_tags
from sklearn.cluster import KMeans, MiniBatchKMeans
from sklearn.metrics.pairwise import cosine_similarity


class Clustering:

    def __init__(self,
                 docs: List[dict],
                 vectorizer="TfIdf Vectorizer",
                 num_clusters=10,
                 clustering_algorithm="kmeans",
                 stop_words=[],
                 num_dims=1000,
                 use_lsi=False,
                 num_topics=50,
                 phraser=None):

        self.algorithm = clustering_algorithm
        self.num_clusters = num_clusters
        self.custom_stop_words = stop_words
        self.docs = docs  # list of dicts
        self.vectorizer = vectorizer
        self.num_dims = num_dims
        self.use_lsi = use_lsi
        self.num_topics = num_topics
        self.ignore_doc_ids = []
        self.phraser = phraser

        self.clustering_result = defaultdict(list)
        self.tfidf_model = None
        self.lsi_model = None
        self.dictionary = None
        self.doc_vectors = {}


    def to_json(self):
        return {
            "algorithm": self.algorithm,
            "num_clusters": self.num_clusters,
            "custom_stop_words": self.custom_stop_words,
            "docs": self.docs,
            "vectorizer": self.vectorizer,
            "num_dims": self.num_dims,
            "use_lsi": self.use_lsi,
            "num_topics": self.num_topics,
            "ignore_doc_ids": self.ignore_doc_ids,
            "clustering_result": self.clustering_result,
            "doc_vectors": self.doc_vectors
        }


    @staticmethod
    def _tokenize(document: dict, phraser=None):
        text_information = [value for key, value in document.items()]
        text = " ".join(text_information)


        def _custom_strip_short(s):
            return strip_short(s, minsize=2)


        def _custom_strip_numeric(s):
            RE_NUMERIC = re.compile(r' [0-9]+( [0-9]+)*(\.)? ', re.UNICODE)
            s = utils.to_unicode(s)
            return RE_NUMERIC.sub(" ", s)


        # most of the preprocessing is done already
        # strip_tags removes style definitions etc as well which is good
        CUSTOM_FILTERS = [strip_tags, _custom_strip_short, _custom_strip_numeric]
        preprocessed_text = preprocess_string(text, CUSTOM_FILTERS)

        if phraser:
            tokens = phraser.phrase(preprocessed_text)
            return [token.replace(' ', '_') for token in tokens]
        else:
            return preprocessed_text


    def _get_vectors(self):
        processed_corpus = [self._tokenize(doc["document"], self.phraser) for doc in self.docs]
        self.dictionary = corpora.Dictionary(processed_corpus)

        # ignore 20% most frequent words
        # num_unique_words = len(dictionary)
        # dictionary.filter_n_most_frequent(int(num_unique_words*0.2))

        # do some more filtering and keep only n most frequent specified with num_dims parameter
        self.dictionary.filter_extremes(no_below=1, no_above=0.8, keep_n=self.num_dims)

        bow_corpus = [self.dictionary.doc2bow(text) for text in processed_corpus]

        if self.vectorizer == "TfIdf Vectorizer":
            self.tfidf_model = models.TfidfModel(bow_corpus)
            transformed_corpus = self.tfidf_model[bow_corpus]
        elif self.vectorizer == "Count Vectorizer":
            transformed_corpus = bow_corpus

        if self.use_lsi:
            self.lsi_model = models.LsiModel(transformed_corpus, id2word=self.dictionary, num_topics=self.num_topics)
            transformed_corpus = self.lsi_model[transformed_corpus]

        matrix = corpus2csc(transformed_corpus, num_terms=len(self.dictionary.keys()), num_docs=self.dictionary.num_docs)
        return matrix.transpose()


    def cluster(self):
        """
        Clusters texts in self.texts & update clustering_result
        """
        vectors = self._get_vectors()

        if self.algorithm == "kmeans":
            labels = KMeans(n_clusters=self.num_clusters, random_state=10).fit_predict(vectors)
        elif self.algorithm == "minibatchkmeans":
            labels = MiniBatchKMeans(n_clusters=self.num_clusters, random_state=10).fit_predict(vectors)

        for ix, doc in enumerate(self.docs):
            self.clustering_result[int(labels[ix])].append(doc["id"])
            self.doc_vectors[doc["id"]] = vectors[ix].toarray()[0]


    def exclude_doc_from_cluster(self, cluster_id, document_id):
        """
        Removes document from a cluster in clustering results.
        :param: int cluster_id: ID of the cluster.
        :param: int document_id: ID of the document to be removed.
        """

        self.clustering_result[cluster_id].pop(self.clustering_result[cluster_id].index(document_id))


    def tag_cluster_documents(self, cluster_id, fact_name, fact_value, index):
        """
        Adds tag as texta_fact to all documents in cluster.
        :param: int cluster_id: ID of the cluster to be tagged.
        :param: str fact_name: Name of the fact.
        :param: str fact_value: Value of the fact.
        :param: str index: Name of the index where documents to be tagged reside.
        """
        # get cluster elements by given id
        # add texta_fact to elasticsearch
        # add document id-s of the cluster elements to self.ignore_doc_ids

        pass


    def save_transformation(self, file_path):
        with open(file_path, "wb") as f:
            pickle.dump({
                "tfidf_model": self.tfidf_model,
                "lsi_model": self.lsi_model,
                "dictionary": self.dictionary,
                "doc_vectors": self.doc_vectors
            }, f)

        return True


class ClusterContent:
    def __init__(self, doc_ids, models=None, vectors_filepath=""):
        self.doc_ids = doc_ids
        self.vectors_filepath = vectors_filepath
        self.models = self._get_models(models, vectors_filepath)


    def _get_models(self, models, vectors_filepath):
        if models is None:
            return self._load_models(vectors_filepath)
        else:
            return models


    def _load_models(self, file_path):
        with open(file_path, "rb") as f:
            models = pickle.load(f)
        return models


    def _save_updated_models(self):
        with open(self.vectors_filepath, "wb") as f:
            pickle.dump(self.models, f)


    def get_intracluster_similarity(self, new_documents=[], phraser=None):
        if len(new_documents) > 0:
            dictionary = self.models["dictionary"]

            for doc in new_documents:
                processed_text = Clustering._tokenize(doc["text"], phraser=phraser)
                doc_vec = [dictionary.doc2bow(processed_text)]

                if self.models["tfidf_model"] is not None:
                    doc_vec = self.models["tfidf_model"][doc_vec]

                if self.models["lsi_model"] is not None:
                    doc_vec = self.models["lsi_model"][doc_vec]

                full_vec = corpus2csc(doc_vec, num_terms=len(dictionary.keys()), num_docs=dictionary.num_docs)
                full_vec = full_vec.transpose()
                self.models["doc_vectors"][doc["id"]] = full_vec[0].toarray()[0]

            self._save_updated_models()

        if self.doc_ids:
            cluster_vectors = []
            for doc_id in self.doc_ids:
                cluster_vectors.append(self.models["doc_vectors"][doc_id])
            similarities = cosine_similarity(cluster_vectors)
            return np.mean(similarities)
        else:
            return 0
