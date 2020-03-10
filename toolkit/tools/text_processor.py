from toolkit.core.lexicon.models import Lexicon
from toolkit.settings import BASE_DIR
import requests
import os


class StopWords:
    """
    Stop word remover using existing lists.
    """
    def __init__(self, custom_stop_words=[]):
        self.stop_words = self._get_stop_words(custom_stop_words)
    
    @staticmethod
    def _get_stop_words(custom_stop_words):
        stop_words = {}
        stop_word_dir = os.path.join(BASE_DIR, 'toolkit', 'tools', 'stop_words')
        for f in os.listdir(stop_word_dir):
            with open('{0}/{1}'.format(stop_word_dir, f), encoding="utf8") as fh:
                for stop_word in fh.read().strip().split('\n'):
                    stop_words[stop_word] = True

        for custom_stop_word in custom_stop_words:
            stop_words[custom_stop_word] = True     

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

    def __init__(self, lemmatizer=None, phraser=None, remove_stop_words=True, sentences=False, tokenize=False, custom_stop_words=[]):
        self.lemmatizer = lemmatizer
        self.phraser = phraser
        self.remove_stop_words = remove_stop_words
        self.sentences = sentences
        self.tokenize = tokenize

        self.stop_words = StopWords(custom_stop_words=custom_stop_words)
    
    def process(self, input_text):
        if isinstance(input_text, str):
            stripped_text = input_text.strip()
            if self.sentences:
                list_of_texts = stripped_text.split('\n')
            else:
                list_of_texts = [stripped_text]
        else:
            # whetever obscure was found, output is as string
            list_of_texts = [str(input_text)]
        out = []
        for text in list_of_texts:
            if text:
                # make sure it is a string
                text = str(text)
                # lemmatize if asked
                if self.lemmatizer:
                    text = self.lemmatizer.lemmatize(text)
                # lower & strip
                text = text.lower().strip()
                # convert string to list of tokens
                tokens = text.split(' ')
                # remove stop words
                if self.remove_stop_words:
                    tokens = self.stop_words.remove(tokens)
                # use phraser
                if self.phraser:
                    tokens = self.phraser.phrase(tokens)
                # remove empty tokens
                tokens = [token for token in tokens if token]
                # prepare output
                if not self.tokenize:
                    out.append(' '.join([token.replace(' ', '_') for token in tokens]))
                else:
                    out.append(tokens)
        return out
