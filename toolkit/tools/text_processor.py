from toolkit.core.lexicon.models import Lexicon
from toolkit.settings import BASE_DIR
import requests
import os

class StopWords:
    """
    Stop word remover using existing lists.
    """
    def __init__(self, lexicon_ids=[]):
        self.stop_words = self._get_stop_words(lexicon_ids)
    
    @staticmethod
    def _get_stop_words(lexicon_ids):
        stop_words = {}
        stop_word_dir = os.path.join(BASE_DIR, 'toolkit', 'tools', 'stop_words')
        for f in os.listdir(stop_word_dir):
            with open('{0}/{1}'.format(stop_word_dir,f),encoding="utf8") as fh:
                for stop_word in fh.read().strip().split('\n'):
                    stop_words[stop_word] = True

        # load lexicons
        lexicons = Lexicon.objects.filter(id__in=lexicon_ids)
        for lexicon in lexicons:
            for phrase in lexicon.phrases.split('\n'):
                phrase = phrase.strip()
                stop_words[phrase] = True       

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

    def __init__(self, phraser=None, remove_stop_words=True, sentences=False, tokenize=False, stop_word_lexicons=[]):
        self.phraser = phraser
        self.remove_stop_words = remove_stop_words
        self.sentences = sentences
        self.tokenize = tokenize

        self.stop_words = StopWords(lexicon_ids=stop_word_lexicons)
    
    def process(self, input_text):
        stripped_text = input_text.strip().lower()
        if self.sentences:
            list_of_texts = stripped_text.split('\n')
        else:
            list_of_texts = [stripped_text]

        out = []

        for text in list_of_texts:
            if text:
                tokens = text.split(' ')
                if self.remove_stop_words:
                    tokens = self.stop_words.remove(tokens)
                if self.phraser:
                    tokens = self.phraser.phrase(tokens)

                if not self.tokenize:
                    out.append(' '.join([token.replace(' ', '_') for token in tokens]))
                else:
                    out.append(tokens)
        
        return out
