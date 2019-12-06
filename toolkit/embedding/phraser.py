from gensim.models.phrases import Phrases
from gensim.models.phrases import Phraser as GSPhraser
import json

from toolkit.embedding.models import Embedding


class Phraser:

    def __init__(self, embedding_id):
        self.embedding_id = embedding_id
        self._phraser = None 
    
    def build(self, sentences):
        phrase_model = Phrases(sentences)
        phraser = GSPhraser(phrase_model)
        self._phraser = phraser

    def save(self, file_path):
        if self._phraser:
            self._phraser.save(file_path)
            return True
        return False

    def load(self):
        embedding_object = Embedding.objects.get(pk=self.embedding_id)
        phraser_location = embedding_object.phraser_model.path
        self._phraser = GSPhraser.load(phraser_location)

    def phrase(self, text):
        if self._phraser:
            if isinstance(text, str):
                text = text.split(' ')
                return ' '.join(self._phraser[text])
            else:
                return self._phraser[text]
        else:
            return text