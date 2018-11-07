from sklearn.feature_extraction.text import CountVectorizer,TfidfVectorizer
from sklearn.cluster import AgglomerativeClustering,KMeans
from sklearn.metrics.pairwise import cosine_similarity
from itertools import combinations
from time import time
from utils.highlighter import Highlighter
import numpy as np
import json
import re

from lexicon_miner.models import Lexicon,Word
from searcher.view_functions.general.searcher_utils import additional_option_cut_text


class ClusterManager:
    """ Manage Cluster Searches
    """
    def __init__(self,es_m,params):
        self.es_m = es_m
        self.params = self._parse_params(params)
        self.documents,self.document_ids = self._scroll_documents(limit=int(self.params['cluster_n_samples']))
        self.document_vectors,self.feature_names = self._vectorize_documents(method=params['cluster_vectorizer'], max_features=int(params['cluster_n_features']))
        self.clusters = self._cluster_documents()
        self.cluster_keywords = self._get_cluster_top_keywords(int(params['cluster_n_keywords']))
        #self.cluster_keywords = self._get_keywords(int(params['cluster_n_keywords']))


    @staticmethod
    def _parse_params(params):
        params_out = {}

        for param in params.keys(): # NEW PY REQUIREMENT
            if 'cluster' in param:
                if param in ['cluster_lexicons']:
                    params_out[param] = params.getlist(param)
                else:
                    params_out[param] = params[param]

        return params_out


    def _scroll_documents(self,limit=1000):
        documents = []
        es_ids = []
        field = json.loads(self.params['cluster_field'])['path']
        response = self.es_m.scroll(field_scroll=field,size=500)
        scroll_id = response['_scroll_id']
        hits = response['hits']['hits']

        i = 0

        while hits:
            hits = response['hits']['hits']
            for hit in hits:
                try:
                    content = hit['_source']
                    for subfield_name in field.split('.'):
                        content = content[subfield_name]
                    documents.append(content)
                    es_ids.append(hit['_id'])

                    i+=1
                    if i == limit:
                        return documents,es_ids
                except:
                    KeyError

            response = self.es_m.scroll(scroll_id=scroll_id)
            scroll_id = response['_scroll_id']

        return documents,es_ids


    def _vectorize_documents(self,method='tfidf',max_features=1000):
        stop_words = []

        try:
            for lexicon_id in self.params['cluster_lexicons']:
                lexicon = Lexicon.objects.get(id=int(lexicon_id))
                words = Word.objects.filter(lexicon=lexicon)
                stop_words+=[word.wrd for word in words]
        except:
            KeyError

        if method == 'count':
            vectorizer = CountVectorizer(analyzer='word', max_features=max_features, stop_words=stop_words)
        if method == 'tfidf':
            vectorizer = TfidfVectorizer(analyzer='word', max_features=max_features, stop_words=stop_words)

        document_vectors = vectorizer.fit_transform(self.documents)
        document_vectors = document_vectors.toarray()

        return document_vectors,vectorizer.get_feature_names()


    def _cluster_documents(self):

        method = self.params['cluster_method']
        n_clusters = int(self.params['cluster_n_clusters'])

        n_samples = len(self.document_vectors)

        if n_clusters > n_samples:
            n_clusters = n_samples

        if method == 'kmeans':
            clusterer = KMeans(n_clusters=n_clusters, init='k-means++', max_iter=100, n_init=1)
        else:
            clusterer = AgglomerativeClustering(n_clusters=n_clusters, linkage='complete', affinity='cosine')

        clustering = clusterer.fit(self.document_vectors)
        cluster_labels = clustering.labels_

        clustering_dict = clustering.__dict__
        # cluster_centers = clustering_dict['cluster_centers_']

        clusters = {}

        for document_id,cluster_label in enumerate(cluster_labels):
            if cluster_label not in clusters:
                clusters[cluster_label] = []
            clusters[cluster_label].append(document_id)

        return clusters#,cluster_centers

    def _get_cluster_top_keywords(self, keywords_per_cluster=10):
        """Shows the top k words for each cluster

        Keyword Arguments:
            keywords_per_cluster {int} -- The k words to show for each cluster (default: {10})

        Returns:
            dict of lists -- Returns a dict of {cluster_id: ['top', 'k', 'words', 'for', 'cluster']}
        """

        out = {}
        docs_for_cluster = {}
        # self.clusters = 10 clusters,containing the index of the document_vectors document in that cluster, ex len(self.clusters[6]) == 508
        for cluster in self.clusters:
            # To flatten/combine all documents into one
            docs_for_cluster[cluster] = np.array([self.document_vectors[i] for i in self.clusters[cluster]])
            # Cluster vectors to feature words
            out[cluster] = np.array(self.feature_names)[np.flip(np.argsort(docs_for_cluster[cluster]), -1)]
            cluster_shape = out[cluster].shape
            out[cluster] = out[cluster].reshape(cluster_shape[0] * cluster_shape[1])[:keywords_per_cluster].tolist()
            # To append seperate document values
            #out[cluster] = np.array(self.feature_names)[np.argsort(docs_for_cluster[cluster])[::-1]][:,:keywords_per_cluster]
        return out


    def highlight_cluster_keywords(self, documents, keywords):
        out = []
        for document in documents:
            to_highlighter = []
            for keyword in keywords:
                pattern = re.compile(u'{0}{1}{2}'.format(u'(?<![A-z0-9])',re.escape(keyword.lower()),u'(?![A-z0-9])'))
                for match in pattern.finditer(document.lower()):
                    span = [(match.start(),match.end())]
                    new_match = {u'spans':span,u'color':u'#FFD119'}
                    to_highlighter.append(new_match)

            if to_highlighter:
                hl = Highlighter(default_category='[HL]')
                document = hl.highlight(document,to_highlighter)
                if 'show_short_version_cluster' in self.params.keys():
                    document = additional_option_cut_text(document, self.params['short_version_n_char_cluster'])
                out.append(document)
            elif not 'show_unhighlighted' in self.params.keys():
                out.append(document)
        return out


    def convert_clustering_data(self):
        out = []
        clusters = self.clusters

        for cluster_id,cluster_content in clusters.items():
            documents = [self.documents[doc_id] for doc_id in cluster_content]
            cluster_label = 'Cluster {0} ({1})'.format(cluster_id+1,len(cluster_content))
            keywords = self.cluster_keywords[cluster_id]
            cluster_data = {'documents':self.highlight_cluster_keywords(documents,keywords),
                            'label':cluster_label,
                            'id':cluster_id,
                            'keywords':' '.join(keywords)}
            out.append(cluster_data)
        return out

    # REPLACED BY _get_cluster_top_keywords()
    # def _get_keywords(self,keywords_per_cluster=10):
    #     out = {}

    #     # loops over 10 clusters, 100 values, probs pointing to words
    #     for cluster_id,cluster in enumerate(self.cluster_centers):
    #         if len(cluster) > keywords_per_cluster:
    #             # get index values of the keywords;
    #             # np.argpartition seperates big and small numbers at some index location, ex: np.array([0, 9, 0, 1, 5, 2])[np.argpartition([0, 9, 0, ((1)), 5, 2], 3)[:3]] > [0, 0, 1]
    #             # get top k biggest values, in random order
    #             keyword_ids = np.argpartition(-cluster,keywords_per_cluster)
    #             # crop the 100 words to some top 10 words
    #             keyword_ids = keyword_ids[:keywords_per_cluster]
    #         else:
    #             keyword_ids = np.argpartition(-cluster,len(cluster)-1)

    #         keywords = [self.feature_names[kw_id] for kw_id in keyword_ids]
    #         out[cluster_id] = keywords
    #     return out
