from sklearn.cluster import MiniBatchKMeans
import numpy as np

class WordCluster(object):
    """
    WordCluster object to cluster Word2Vec vectors using MiniBatchKMeans.
    : param embedding : Word2Vec object
    : param n_clusters, int, number of clusters in output
    """
    def __init__(self, embedding, n_clusters=None):
        self.word_to_cluster_dict = {}
        self.cluster_dict = {}
        self.clustering = None
        self._start(embedding, n_clusters)
    
    def _start(self, embedding, n_clusters):
        vocab = list(embedding.wv.vocab.keys())
        vocab_vectors = np.array([embedding[word] for word in vocab])
        
        if not n_clusters:
            # number of clusters = 10% of embedding vocabulary
            # if larger than 5000, limit to 5000
            n_clusters = int(len(vocab) * 0.1)
            if n_clusters > 5000:
                n_clusters = 5000

        self.clustering = MiniBatchKMeans(n_clusters=n_clusters).fit(vocab_vectors)
        cluster_labels = self.clustering.labels_
        
        for i,cluster_label in enumerate(cluster_labels):
            word = vocab[i]
            etalon = embedding.wv.most_similar(positive=[self.clustering.cluster_centers_[cluster_label]])[0][0]
            
            if etalon not in self.cluster_dict:
                self.cluster_dict[etalon] = []
                
            self.cluster_dict[etalon].append(word)
            self.word_to_cluster_dict[word] = etalon
    
    def query(self, word):
        try:
            return self.cluster_dict[self.word_to_cluster_dict[word]]
        except:
            return []
    
    def text_to_clusters(self, text):
        text = [str(self.word_to_cluster_dict[word]) for word in text if word in self.word_to_cluster_dict]
        return ' '.join(text)
