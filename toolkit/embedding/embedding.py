from gensim.models import word2vec
import json

from toolkit.embedding.models import Embedding

class W2VEmbedding:

    def __init__(self, embedding_id, name=None):
        self.model = None
        self.name = name
        self.embedding_id = embedding_id
    
    def load(self):
        """
        Load embedding from file system
        """
        if not self.embedding_id:
            return False

        embedding_object = Embedding.objects.get(pk=self.embedding_id)
        file_path = json.loads(embedding_object.location)['embedding']
        model = word2vec.Word2Vec.load(file_path)
        self.model = model
        self.name = embedding_object.description
        return True
    
    def similarity(self):
        """
        Compute similarity for input pair
        """
        pass

    def get_similar(self, text_input, n=20):
        """
        Find similar objects to the input from the embedding
        """

        if isinstance(text_input, list):
            positives = [text.replace(' ', '_') for text in text_input]
        else:
            positives = [text_input.replace(' ', '_')]
        
        positives = [positive for positive in positives if positive in self.model.wv.vocab]
        
        if positives:
            similar_items = self.model.wv.most_similar(positive=positives, topn=n)
            similar_items = [{'phrase':s[0].replace('_', ' '), 'score':s[1], 'model': self.name} for s in similar_items]
            return similar_items
        else:
            return []
    
    def get_vector(self, word):
        """
        Get vector for given embedding entry
        """
        return self.model[word]
    
    def get_vocabulary(self):
        """
        Get embedding vocabulary
        """
        return self.model.wv.index2word
