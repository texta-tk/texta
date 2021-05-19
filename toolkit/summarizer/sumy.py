import re
import ast
import logging
from typing import List
from pelecanus import PelicanJson
from sumy.nlp.stemmers import null_stemmer
from sumy.parsers.plaintext import PlaintextParser
from texta_tools.text_processor import StopWords
from toolkit.settings import ERROR_LOGGER


class SumyTokenizer:
    """
    Custom tokenizer for sumy.
    """

    @staticmethod
    def sentences_ratio(text, ratio):
        tkns = list(filter(bool, text.split(".")))
        count = len(tkns)
        return float(count * ratio)

    @staticmethod
    def to_sentences(text):
        return filter(bool, re.split(r'(?<=\.) ', text))

    @staticmethod
    def to_words(sentence):
        return sentence.lower().split()


class Sumy:
    def __init__(self):
        self.stop_words = StopWords()

    def get_summarizers(self, names):
        """Retrieves sumy summarizers algorithms

            Parameters:
            names (list): list of summarizer algorithm names

            Returns:
            dict:summarizers

        """
        summarizers = {}
        for name in names:
            if name == "random":
                from sumy.summarizers.random import RandomSummarizer
                summarizers["random"] = RandomSummarizer(null_stemmer)
            elif name == "luhn":
                from sumy.summarizers.luhn import LuhnSummarizer
                summarizers["luhn"] = LuhnSummarizer(stemmer=null_stemmer)
            elif name == "lsa":
                from sumy.summarizers.lsa import LsaSummarizer
                summarizers["lsa"] = LsaSummarizer(stemmer=null_stemmer)
            elif name == "lexrank":
                from sumy.summarizers.lex_rank import LexRankSummarizer
                summarizers["lexrank"] = LexRankSummarizer(null_stemmer)
            elif name == "textrank":
                from sumy.summarizers.text_rank import TextRankSummarizer
                summarizers["textrank"] = TextRankSummarizer(null_stemmer)
            elif name == "sumbasic":
                from sumy.summarizers.sum_basic import SumBasicSummarizer
                summarizers["sumbasic"] = SumBasicSummarizer(null_stemmer)
            elif name == "kl-sum":
                from sumy.summarizers.kl import KLSummarizer
                summarizers["kl-sum"] = KLSummarizer(null_stemmer)
            elif name == "reduction":
                from sumy.summarizers.reduction import ReductionSummarizer
                summarizers["reduction"] = ReductionSummarizer(null_stemmer)

        for _, summarizer in summarizers.items():
            summarizer.stop_words = frozenset(self.stop_words._get_stop_words(custom_stop_words=[]))

        return summarizers

    def run_on_tokenized(self, text, summarizer_names, ratio):
        """Generate summary based on tokenized text

            Parameters:
            text (str): plain text
            summarizer_names (list): list of summarizer algorithms to use
            ratio (float): ratio to use for summarization

            Returns:
            list:stack

        """
        summarizers = self.get_summarizers(summarizer_names)

        stack = []
        if float(ratio) <= 1:
            ratio_count = SumyTokenizer().sentences_ratio(text, float(ratio))
        else:
            ratio_count = ratio
        parser = PlaintextParser.from_string(text, SumyTokenizer())

        summaries = {}
        for name, summarizer in summarizers.items():
            try:
                summarization = summarizer(parser.document, float(ratio_count))
            except Exception as e:
                logging.getLogger(ERROR_LOGGER).exception(e)
                continue

            summary = [sent._text for sent in summarization]
            summary = "\n".join(summary)
            summaries[name] = summary

        stack.append(summaries)

        return stack

    def run_on_index(self, docs: List[dict], doc_paths: List[str], ratio, algorithm: List[str]):
        """Generate summary based on tokenized text retrieved from es fields

            Parameters:
            docs (list): list of documents
            doc_paths (list): list of fields
            ratio (float): ratio to use for summarization
            algorithm (list): list of algorithms for sumy

            Returns:
            list:stack

        """
        stack = []
        algorithm = ast.literal_eval(algorithm)
        summarizers = self.get_summarizers(algorithm)
        for document in docs:
            wrapper = PelicanJson(document)
            for doc_path in doc_paths:
                doc_path_as_list = doc_path.split(".")
                content = wrapper.safe_get_nested_value(doc_path_as_list, default=[])
                if content and isinstance(content, str):
                    ratio_count = SumyTokenizer().sentences_ratio(content, float(ratio))
                    parser = PlaintextParser.from_string(content, SumyTokenizer())
                else:
                    ratio_count = SumyTokenizer().sentences_ratio(document[doc_path], float(ratio))
                    parser = PlaintextParser.from_string(document[doc_path], SumyTokenizer())

                summaries = {}
                for name, summarizer in summarizers.items():
                    try:
                        summarization = summarizer(parser.document, float(ratio_count))
                    except Exception as e:
                        logging.getLogger(ERROR_LOGGER).exception(e)
                        continue

                    summary = [sent._text for sent in summarization]
                    summary = "\n".join(summary)
                    summaries[doc_path + "_" + name] = summary

                stack.append(summaries)

        return stack
