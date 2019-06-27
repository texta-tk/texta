from sklearn.cluster import MiniBatchKMeans
import numpy as np
import json
import os

from toolkit.word_cluster.models import WordCluster as WordClusterInstance
from toolkit.settings import MODELS_DIR

class WordCluster(object):
    """
    WordCluster object to cluster Word2Vec vectors using MiniBatchKMeans.
    : param embedding : Word2Vec object
    : param n_clusters, int, number of clusters in output
    """
    def __init__(self, clustering_id):
        self.word_to_cluster_dict = {}
        self.cluster_dict = {}
        self.clustering_id = clustering_id
    
    def cluster(self, embedding, n_clusters):
        embedding = embedding.model
        vocab = list(embedding.wv.vocab.keys())
        vocab_vectors = np.array([embedding[word] for word in vocab])

        clustering = MiniBatchKMeans(n_clusters=n_clusters).fit(vocab_vectors)
        cluster_labels = clustering.labels_
        
        print('computing etalons')
        etalons = {cluster_label: embedding.wv.most_similar(positive=[clustering.cluster_centers_[cluster_label]])[0][0] for cluster_label in set(cluster_labels)}

        print('finishing toutches...')

        for i,cluster_label in enumerate(cluster_labels):
            word = vocab[i]
            etalon = etalons[cluster_label]
            if etalon not in self.cluster_dict:
                self.cluster_dict[etalon] = []
            self.cluster_dict[etalon].append(word)
            self.word_to_cluster_dict[word] = etalon
        
        return True
    
    def query(self, word):
        try:
            return self.cluster_dict[self.word_to_cluster_dict[word]]
        except:
            return []
    
    def text_to_clusters(self, text):
        text = [str(self.word_to_cluster_dict[word]) for word in text.split(' ') if word in self.word_to_cluster_dict]
        return ' '.join(text)

    def save(self, file_path):
        try:
            data = {"word_to_cluster_dict": self.word_to_cluster_dict, "cluster_dict": self.cluster_dict}
            with open(file_path, 'w') as fh:
                fh.write(json.dumps(data))
            return True
        except:
            return False
    
    def load(self):
        """
        Load word cluster from file system
        """
        if not self.clustering_id:
            return False

        clustering_object = WordClusterInstance.objects.get(pk=self.clustering_id)
        file_path = json.loads(clustering_object.location)['cluster']
        with open(file_path) as fh:
            loaded_json = json.loads(fh.read())
            self.cluster_dict = loaded_json['cluster_dict']
            self.word_to_cluster_dict = loaded_json['word_to_cluster_dict']
        return True
