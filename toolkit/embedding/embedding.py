from gensim.models import word2vec, KeyedVectors
from torch import FloatTensor
import json

from gensim.models import word2vec

from toolkit.embedding.models import Embedding


class W2VEmbedding:

    def __init__(self, embedding_id, name=None):
        self.model = None
        self.name = name
        self.embedding_id = embedding_id


    def load(self):
        """
        Loads embedding from file system.
        """
        if not self.embedding_id:
            return False

        embedding_object = Embedding.objects.get(pk=self.embedding_id)
        file_path = json.loads(embedding_object.location)['embedding']
        # load model using KeyedVector module to reduce memory usage
        model = KeyedVectors.load(file_path)
        self.model = model
        self.name = embedding_object.description
        return True

    def tensorize(self):
        """
        Returns vectors as FloatTensor and word2index dict for torchtext Vocab object. We can use embeddings in torch taggers!
        https://torchtext.readthedocs.io/en/latest/vocab.html
        """
        word2index = {token: token_index for token_index, token in enumerate(self.model.wv.index2word)}
        return FloatTensor(self.model.wv.vectors), word2index


    def similarity(self):
        """
        Returns similarity for input pair.
        """
        pass


    def get_similar(self, positives, negatives=[], n=20):
        """
        Find similar words & phraser for input list of strings.
        """
        positives = [positive.replace(' ', '_') for positive in positives]
        negatives = [negative.replace(' ', '_') for negative in negatives]

        # filter out words not present in the embedding vocabulary
        positives = [positive for positive in positives if positive in self.model.wv.vocab]
        negatives = [negative for negative in negatives if negative in self.model.wv.vocab]

        if positives:
            similar_items = self.model.wv.most_similar(positive=positives, negative=negatives, topn=n)
            similar_items = [{'phrase': s[0].replace('_', ' '), 'score': s[1], 'model': self.name} for s in similar_items if s[0] not in negatives]
            return similar_items
        else:
            return []


    def get_vector(self, word):
        """
        Returns vector for given embedding entry.
        """
        return self.model[word]


    def get_vocabulary(self):
        """
        Returns embedding vocabulary from KeyedVectors.
        """
        return self.model.wv.index2word
