from toolkit.settings import BASE_DIR
import requests
import os

class StopWords:
    """
    Stop word remover
    """
    def __init__(self):
        self.stop_words = self._get_stop_words()
    
    @staticmethod
    def _get_stop_words():
        stop_words = {}
        stop_word_dir = os.path.join(BASE_DIR, 'toolkit', 'tools', 'stop_words')
        for f in os.listdir(stop_word_dir):
            with open('{0}/{1}'.format(stop_word_dir,f),encoding="utf8") as fh:
                for stop_word in fh.read().strip().split('\n'):
                    stop_words[stop_word] = True
        return stop_words

    
    def remove(self, text):
        if isinstance(text, str):
            return ' '.join([lemma for lemma in text.split(' ') if lemma not in self.stop_words])
        elif isinstance(text, list):
            return [lemma for lemma in text if lemma not in self.stop_words]
        else:
            return None


class TextProcessor:
    """
    Processor for processing texts prior to modelling
    """

    def __init__(self, phraser=None, remove_stop_words=True, sentences=False):
        self.phraser = phraser
        self.remove_stop_words = remove_stop_words
        self.sentences = sentences
        self.stop_words = StopWords()
    
    def process(self, text):
        text = text.strip().lower()
        if self.remove_stop_words:
            text = self.stop_words.remove(text)
        if self.phraser:
            text = ' '.join(self.phraser.phrase(text))
        if not self.sentences:
            return text
        else:
            return [word for word in text.split('\n') if word.strip()]