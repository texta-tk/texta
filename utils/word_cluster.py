from sklearn.cluster import MiniBatchKMeans
import numpy as np
import json
import os

from texta.settings import MODELS_DIR

class WordCluster(object):
    """
    WordCluster object to cluster Word2Vec vectors using MiniBatchKMeans.
    : param embedding : Word2Vec object
    : param n_clusters, int, number of clusters in output
    """
    def __init__(self):
        self.word_to_cluster_dict = {}
        self.cluster_dict = {}
    
    def cluster(self, embedding, n_clusters=None):
        vocab = list(embedding.wv.vocab.keys())
        vocab_vectors = np.array([embedding[word] for word in vocab])
        
        if not n_clusters:
            # number of clusters = 10% of embedding vocabulary
            # if larger than 1000, limit to 1000
            n_clusters = int(len(vocab) * 0.1)
            if n_clusters > 1000:
                n_clusters = 1000

        clustering = MiniBatchKMeans(n_clusters=n_clusters).fit(vocab_vectors)
        cluster_labels = clustering.labels_
        
        for i,cluster_label in enumerate(cluster_labels):
            word = vocab[i]
            etalon = embedding.wv.most_similar(positive=[clustering.cluster_centers_[cluster_label]])[0][0]
            
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
        text = [str(self.word_to_cluster_dict[word]) for word in text if word in self.word_to_cluster_dict]
        return ' '.join(text)

    def save(self, file_path):
        try:
            data = {"word_to_cluster_dict": self.word_to_cluster_dict, "cluster_dict": self.cluster_dict}
            with open(file_path, 'w') as fh:
                fh.write(json.dumps(data))
            return True
        except:
            return False
    
    def load(self, unique_id, task_type='train_tagger'):
        file_path = os.path.join(MODELS_DIR, task_type, 'cluster_{}'.format(unique_id))
        try:
            with open(file_path) as fh:
                data = json.loads(fh.read())
            self.cluster_dict = data["cluster_dict"]
            self.word_to_cluster_dict = data["word_to_cluster_dict"]
        except:
            return False
