import pickle
from collections import defaultdict

import numpy as np
from gensim import corpora, models
from gensim.matutils import corpus2csc
from gensim.parsing.preprocessing import preprocess_string, strip_multiple_whitespaces, strip_punctuation, strip_short, strip_tags
from sklearn.cluster import KMeans, MiniBatchKMeans
from sklearn.metrics.pairwise import cosine_similarity


class Clustering:

    def __init__(self,
                 docs,
                 vectorizer="TfIdf Vectorizer",
                 num_clusters=10,
                 clustering_algorithm="minibatchkmeans",
                 stop_words=[],
                 num_dims=1000,
                 use_lsi=False,
                 num_topics=50):

        self.algorithm = clustering_algorithm
        self.num_clusters = num_clusters
        self.custom_stop_words = stop_words
        self.docs = docs  # list of dicts
        self.vectorizer = vectorizer
        self.num_dims = num_dims
        self.use_lsi = use_lsi
        self.num_topics = num_topics
        self.ignore_doc_ids = []

        self.clustering_result = {}
        self.vectors = {}


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
            "vectors": self.vectors
        }


    def _tokenize(self, text):
        def _custom_strip_short(s):
            return strip_short(s, minsize=2)


        CUSTOM_FILTERS = [lambda x: x.lower(), strip_tags, strip_punctuation, strip_multiple_whitespaces, _custom_strip_short]
        tokens = preprocess_string(text, CUSTOM_FILTERS)
        return [token for token in tokens if token not in self.custom_stop_words]

    def _get_vectors(self):
        processed_corpus = [self._tokenize(doc["text"]) for doc in self.docs]
        dictionary = corpora.Dictionary(processed_corpus)
        num_unique_words = len(dictionary)
        #ignore 20% most frequent words
        #im not sure whether this is needed as we below filter extremes out anyway but let's keep this right now
        dictionary.filter_n_most_frequent(int(num_unique_words*0.2))
        #do some more filtering and keep only n most frequent specified with num_dims parameter
        dictionary.filter_extremes(no_below=1, no_above=0.8, keep_n=self.num_dims)

        bow_corpus = [dictionary.doc2bow(text) for text in processed_corpus]

        if self.vectorizer == "TfIdf Vectorizer":
            tfidf_model = models.TfidfModel(bow_corpus)
            transformed_corpus = tfidf_model[bow_corpus]
        elif self.vectorizer == "Count Vectorizer":
            transformed_corpus = bow_corpus

        if self.use_lsi:
            lsi_model = models.LsiModel(transformed_corpus, id2word=dictionary, num_topics=self.num_topics)
            transformed_corpus = lsi_model[transformed_corpus]

        matrix = corpus2csc(transformed_corpus, num_terms=len(dictionary.keys()), num_docs=dictionary.num_docs)
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

        result = defaultdict(list)
        for ix, doc in enumerate(self.docs):
            result[int(labels[ix])].append(doc["id"])
            self.vectors[doc["id"]] = vectors[ix].toarray()[0]

        self.clustering_result = result


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


    def save_transformation(self, file_path, vectors: dict = None):
        with open(file_path, "wb") as f:
            if vectors:
                pickle.dump(vectors, f)
            else:
                pickle.dump(self.vectors, f)

        return True


class ClusterContent:
    def __init__(self, doc_ids, vectors=None, vectors_filepath=""):
        self.doc_ids = doc_ids
        self.vectors = self._get_vectors(vectors, vectors_filepath)


    def _get_vectors(self, vectors, vectors_filepath):
        if vectors is None:
            return self._load_vectors(vectors_filepath)
        else:
            return vectors


    def _load_vectors(self, file_path):
        with open(file_path, "rb") as f:
            vectors = pickle.load(f)
        return vectors


    def get_intracluster_similarity(self):
        cluster_vectors = [self.vectors[doc_id] for doc_id in self.doc_ids]
        similarities = cosine_similarity(cluster_vectors)
        return np.mean(similarities)
