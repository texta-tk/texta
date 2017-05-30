from sklearn.feature_extraction.text import CountVectorizer
from sklearn.cluster import AgglomerativeClustering,KMeans
from sklearn.metrics.pairwise import cosine_similarity

from itertools import combinations
from time import time
import numpy as np

import json


class ClusterManager:
    """ Manage Cluster Searches
    """
    def __init__(self,es_m,params):
        self.documents = []
        self.document_vectors = None

        start = time()
        
        self.es_m = es_m
        self.params = self._parse_params(params)

        self._scroll_documents()

        print 'scroll',time()-start
        start = time()
        
        self.document_vectors = self._vectorize_documents()

        print 'vectorization',time()-start
        start = time()

        self.clusters = self._cluster_documents()

        print 'clustering',time()-start
        start = time()


    @staticmethod
    def _parse_params(params):
        params_out = {}

        for param in params:
            if param.startswith('cluster'):
                params_out[param] = params[param]

        return params_out


    def _scroll_documents(self,limit=1000):
        field = json.loads(self.params['cluster_field'])['path']
        response = self.es_m.scroll(field_scroll=field,size=500)
        scroll_id = response['_scroll_id']
        hits = response['hits']['hits']

        i = 0

        while hits:
            hits = response['hits']['hits']
            for hit in hits:

                content = hit['fields'][field][0]
                self.documents.append(content)
                
                i+=1
                if i == limit:
                    return True

            response = self.es_m.scroll(scroll_id=scroll_id)
            scroll_id = response['_scroll_id']

        return True


    def _vectorize_documents(self):
        count_vectorizer = CountVectorizer(analyzer='word', max_features=100)
        document_vectors = count_vectorizer.fit_transform(self.documents)
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


    def create_graph(self):
        vector_len = self.document_vectors.shape[1]
        cluster_ids = self.clusters.keys()
        
        nodes = [{'id':str(cluster_id),'group':cluster_id} for cluster_id in cluster_ids]
        links = []
    
        for combination in combinations(cluster_ids,2):
            vectors_to_compare = []
            for cluster in combination:
                document_vectors_in_cluster = np.zeros((len(self.clusters[cluster]),vector_len))
                for i,document_id in enumerate(self.clusters[cluster]):
                    document_vectors_in_cluster[i] = self.document_vectors[document_id]
                cluster_vector = np.sum(document_vectors_in_cluster,axis=0)
                vectors_to_compare.append(cluster_vector.reshape(1,-1))
                
            similarity = cosine_similarity(vectors_to_compare[0],vectors_to_compare[1])
            
            link = {'source': str(combination[0]),
                    'target': str(combination[1]),
                    'value': similarity[0][0]}
            
            links.append(link)

        return nodes,links

            
