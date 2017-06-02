from sklearn.feature_extraction.text import CountVectorizer,TfidfVectorizer
from sklearn.cluster import AgglomerativeClustering,KMeans
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE, MDS

from gensim.summarization import summarize

from itertools import combinations
from time import time
import numpy as np

import json


class ClusterManager:
    """ Manage Cluster Searches
    """
    def __init__(self,es_m,params):
        self.es_m = es_m
        self.params = self._parse_params(params)

        start = time()
        
        self.documents,self.document_ids = self._scroll_documents()

        print 'scroll',time()-start
        start = time()
        
        self.document_vectors = self._vectorize_documents()

        print 'vectorization',time()-start
        start = time()

        self.clusters = self._cluster_documents()

        print 'clustering',time()-start
        start = time()

        self.cluster_keywords = self._get_keywords()

        print 'keyword extraction',time()-start
        start = time()

    @staticmethod
    def _parse_params(params):
        params_out = {}

        for param in params:
            if param.startswith('cluster'):
                params_out[param] = params[param]

        return params_out


    def _scroll_documents(self,limit=100):
        documents = []
        es_ids = []
        field = json.loads(self.params['cluster_field'])['path']
        response = self.es_m.scroll(field_scroll=field,size=50)
        scroll_id = response['_scroll_id']
        hits = response['hits']['hits']

        i = 0

        while hits:
            hits = response['hits']['hits']
            for hit in hits:

                content = hit['fields'][field][0]
                documents.append(content)
                es_ids.append(hit['_id'])
                
                i+=1
                if i == limit:
                    return documents,es_ids

            response = self.es_m.scroll(scroll_id=scroll_id)
            scroll_id = response['_scroll_id']

        return documents,es_ids


    def _vectorize_documents(self,method='tf',max_features=100):
       
        if method == 'tf':
            vectorizer = TfidfVectorizer(analyzer='word', use_idf=False, max_features=max_features)
        if method == 'tfidf':
            vectorizer = TfidfVectorizer(analyzer='word', max_features=max_features)
        
        document_vectors = vectorizer.fit_transform(self.documents)
        document_vectors = document_vectors.toarray()

        return document_vectors


    def _cluster_documents(self):

        method = self.params['cluster_method']
        n_clusters = int(self.params['cluster_n_clusters'])

        if method == 'kmeans':
            clusterer = KMeans(n_clusters=n_clusters, init='k-means++', max_iter=100, n_init=1)
        else:
            clusterer = AgglomerativeClustering(n_clusters=n_clusters, linkage='complete', affinity='cosine')

        cluster_labels = clusterer.fit(self.document_vectors).labels_

        clusters = {}

        for document_id,cluster_label in enumerate(cluster_labels):
            if cluster_label not in clusters:
                clusters[cluster_label] = []
            clusters[cluster_label].append(document_id)

        return clusters


    def _get_keywords(self):
        keywords = []
        multisearch_queries = []
        for cluster_id,values in self.clusters.items():
            doc_ids = [self.document_ids[value] for value in values]
            path = json.loads(self.params['cluster_field'])['path']

            header = {"index": self.es_m.index}
            body = {"query": {"ids": {"values": doc_ids}}, "aggregations": {"significant_terms": {"significant_terms": {"field": path, "size": 30}}}}

            multisearch_queries.append(json.dumps(header))
            multisearch_queries.append(json.dumps(body))

        responses =  self.es_m.perform_queries(multisearch_queries)
        for response in responses:
            buckets = response['aggregations']['significant_terms']['buckets']
            cluster_keywords = [bucket['key'] for bucket in buckets]
            keywords.append(cluster_keywords)
        return keywords


    def create_graph(self):
        vector_len = self.document_vectors.shape[1]
        cluster_ids = self.clusters.keys()
        
        nodes = [{"title":"asd","group":cluster_id} for cluster_id in cluster_ids]
        links = []
    
        for combination in combinations(cluster_ids,2):
            vectors_to_compare = []
            for cluster in combination:
                document_vectors_in_cluster = np.zeros((len(self.clusters[cluster]),vector_len))
                for i,document_id in enumerate(self.clusters[cluster]):
                    document_vectors_in_cluster[i] = self.document_vectors[document_id]
                cluster_vector = np.sum(document_vectors_in_cluster,axis=0)
                vectors_to_compare.append(cluster_vector.reshape(1,-1))
                
            similarity = cosine_similarity(vectors_to_compare[0],vectors_to_compare[1])[0][0]
            
            link = {"source": combination[0],
                    "target": combination[1],
                    "value": similarity}
            
            links.append(link)

        return nodes,links


    def get_cluster_coords(self):
        cluster_vectors = []
        for cluster in self.clusters.keys():
            cluster_vector = self._vectorize_cluster(cluster)
            cluster_vectors.append(cluster_vector)

        #coords = PCA(n_components=2).fit_transform(cluster_vectors)

        #coords = MDS(n_components=2).fit_transform(cluster_vectors)

        coords = TSNE(n_components=2,metric='cosine',learning_rate=50).fit_transform(cluster_vectors)

        return coords.tolist()
    

    def _vectorize_cluster(self,cluster,method='mean'):
        vector_len = self.document_vectors.shape[1]
        document_vectors_in_cluster = np.zeros((len(self.clusters[cluster]),vector_len))

        for i,document_id in enumerate(self.clusters[cluster]):
            document_vectors_in_cluster[i] = self.document_vectors[document_id]

        if method == 'sum':
            cluster_vector = np.sum(document_vectors_in_cluster,axis=0)
        else:
            cluster_vector = np.mean(document_vectors_in_cluster,axis=0)
        #cluster_vector.reshape(1,-1)
        return cluster_vector
        
