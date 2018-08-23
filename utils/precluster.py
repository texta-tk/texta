from __future__ import print_function
import scipy.spatial.distance as scidist
import scipy.cluster.hierarchy as hier
import numpy as np
import heapq
from sklearn.metrics import silhouette_score

class DataPoint:

    def __init__(self,label,vector):
        self.label = label
        self.vector = vector

    def is_cluster(self):
        return False

class Cluster:

    def __init__(self,left,right,distance):
        self.left = left
        self.right = right
        self.distance = distance

    def is_cluster(self):
        return True

class PreclusterMaker:

    def __init__(self,words, vectors, number_of_steps = 21,metric="cosine",linkage="complete"):
        self.words = words
        self.vectors = vectors
        self.number_of_steps = number_of_steps
        self.metric = metric
        self.linkage = linkage

    def __call__(self):
        if len(self.words) == 0 or len(self.vectors) == 0:
            return []
        if len(self.words) == 1:
            self.words.append(self.words[0])
            self.vectors.append(self.vectors[0])

        distance_matrix = scidist.pdist(np.array(self.vectors),self.metric)
        linkage_matrix = hier.linkage(distance_matrix,self.linkage)

        dendrogram = self._linkage_matrix_to_dendrogram(linkage_matrix,self.words,self.vectors)
        clusterings = self._create_clusterings(dendrogram)
        return [[(node.label,node.vector) for node in _get_cluster_nodes(cluster)] for cluster in self._find_optimal_clustering(clusterings)]

    def _linkage_matrix_to_dendrogram(self,linkage_matrix,labels,vectors):

        N = len(self.words)

        distances = []

        cluster_map = {}
        for i in range(N):
            cluster_map[i] = DataPoint(labels[i],vectors[i])

        next_cluster_idx = N

        # generate clusters of clusters
        for row_idx in range(len(linkage_matrix)):
            step = linkage_matrix[row_idx]
            cluster_map[row_idx+N] = Cluster(cluster_map[int(step[0])],cluster_map[int(step[1])],step[2])
            distances.append(step[2])

        distances.sort()
        self._min_dist = distances[0]
        self._max_dist = distances[-1]
        self._dist_step = (self._max_dist - self._min_dist) / self.number_of_steps

        return cluster_map[row_idx+N if N > 1 else 0]

    def _create_clusterings(self,dendrogram):
        clusterings = [[(-(dendrogram.distance),dendrogram)]]

        for threshold in np.linspace(-self._max_dist,-self._min_dist,self.number_of_steps)[1:]:
            new_clustering = clusterings[-1][:] # set new clustering to be equivalent to previous
            # Expand previous clustering
            while new_clustering[0][0] < threshold and new_clustering[0][1].is_cluster():
                expanded_cluster = heapq.heappop(new_clustering)[1]
                left = expanded_cluster.left
                right = expanded_cluster.right

                if left.is_cluster():
                    heapq.heappush(new_clustering,(-left.distance,left))
                else:
                    heapq.heappush(new_clustering,(-(self._min_dist-1),left))

                if right.is_cluster():
                    heapq.heappush(new_clustering,(-right.distance,right))
                else:
                    heapq.heappush(new_clustering,(-(self._min_dist-1),right))

            clusterings.append(new_clustering)

        return clusterings

    def _find_optimal_clustering(self,clusterings):

        max_score = float('-inf')
        max_clustering = None

        for clustering in clusterings:
            labeled_vectors = [(node.vector,cluster_idx) for cluster_idx in range(len(clustering)) for node in _get_cluster_nodes(clustering[cluster_idx][1]) ]
            vectors,labels = [np.array(x) for x in zip(*labeled_vectors)]
            if np.in1d([1],labels)[0]:
                score = silhouette_score(vectors,labels,metric='cosine')
            else:
                continue # silhouette doesn't work with just one cluster
            if score > max_score:
                max_score = score
                max_clustering = clustering

        return list(zip(*max_clustering))[1] if max_clustering else list(zip(*clusterings[0]))[1]

def _get_cluster_nodes(node):

    if not node.is_cluster():
        return [node]
    else:
        return _get_cluster_nodes(node.left) + _get_cluster_nodes(node.right)

if __name__ == "__main__":
    words = np.arange(20)
    vectors = np.random.rand(20,8)
    print(PreclusterMaker(words,vectors)())