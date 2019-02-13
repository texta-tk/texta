from texta.settings import BASE_DIR
import requests
import os

class StopWords:
    
    def __init__(self):
        self.stop_words = self._get_stop_words()
    
    @staticmethod
    def _get_stop_words():
        stop_words = {}
        stop_word_dir = os.path.join(os.path.abspath(os.path.join(BASE_DIR, os.pardir)), 'utils', 'stop_words')
        for f in os.listdir(stop_word_dir):
            with open('{0}/{1}'.format(stop_word_dir,f)) as fh:
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
