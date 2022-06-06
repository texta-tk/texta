import logging
from typing import Optional

import elasticsearch
from celery.result import allow_join_result
from elasticsearch.client import IndicesClient
from texta_tools.text_splitter import TextSplitter

from texta_elastic.core import ElasticCore
from toolkit.mlp.tasks import apply_mlp_on_list
from toolkit.settings import CELERY_MLP_TASK_QUEUE, ERROR_LOGGER


class CeleryLemmatizer:

    def __init__(self):
        pass


    def lemmatize(self, text):
        with allow_join_result():
            mlp = apply_mlp_on_list.apply_async(kwargs={"texts": [text], "analyzers": ["lemmas"]}, queue=CELERY_MLP_TASK_QUEUE).get()
            lemmas = mlp[0]["text_mlp"]["lemmas"]
            return lemmas


class ElasticAnalyzer:

    def __init__(self, language="english"):
        self.core = ElasticCore()
        self.indices_client = IndicesClient(self.core.es)
        self.splitter = TextSplitter(split_by="WORD_LIMIT")
        self.language = language


    def chunk_input(self, text):
        analyzed_chunks = []
        # Split input if token count greater than 5K.
        # Elastic will complain if token count exceeds 10K.
        docs = self.splitter.split(text, max_limit=5000)
        # Extract text chunks from docs.
        text_chunks = [doc["text"] for doc in docs]
        return text_chunks


    def apply_analyzer(self, body):
        try:
            analysis = self.indices_client.analyze(body=body)
            tokens = [token["token"] for token in analysis["tokens"]]
            token_string = " ".join(tokens)
            return token_string
        except elasticsearch.exceptions.RequestError as e:
            reason = e.info["error"]["reason"]
            if "Invalid stemmer class" in reason:
                logging.getLogger(ERROR_LOGGER).warning(e)
            else:
                logging.getLogger(ERROR_LOGGER).exception(e)
            return ""
        except Exception as e:
            logging.getLogger(ERROR_LOGGER).exception(e)
            return ""


    def _prepare_stem_body(self, text, language, strip_html: bool, tokenizer="standard"):
        body = {"text": text, "tokenizer": tokenizer, "filter": [{"type": "snowball", "language": language}]}
        if strip_html:
            body["char_filter"] = ["html_strip"]
        return body


    def stem_text(self, text: str, language: Optional[str], strip_html=True, tokenizer="standard"):
        analysed_chunks = []
        text_chunks = self.chunk_input(text)
        for chunk in text_chunks:
            body = self._prepare_stem_body(chunk, language, strip_html, tokenizer)
            response = self.apply_analyzer(body)
            analysed_chunks.append(response)
        return " ".join(analysed_chunks)


    def _prepare_tokenizer_body(self, text, tokenizer="standard", strip_html: bool = True):
        body = {"text": text, "tokenizer": tokenizer}
        if strip_html:
            body["char_filter"] = ["html_strip"]
        return body


    def tokenize_text(self, text, tokenizer="standard", strip_html=True):
        analysed_chunks = []
        text_chunks = self.chunk_input(text)
        for chunk in text_chunks:
            body = self._prepare_tokenizer_body(chunk, tokenizer, strip_html)
            response = self.apply_analyzer(body)
            analysed_chunks.append(response)
        return " ".join(analysed_chunks)


    def analyze(self, text: str, body: dict) -> str:
        analysed_chunks = []
        text_chunks = self.chunk_input(text)
        for chunk in text_chunks:
            body = {**body, "text": chunk, }
            response = self.apply_analyzer(body)
            analysed_chunks.append(response)
        return " ".join(analysed_chunks)


    # This only exists here because otherwise it breaks backwards compatibility
    # with the texta-tools library that send there as the lemmatizer.
    def lemmatize(self, text):
        return self.stem_text(text=text, language=self.language, strip_html=True)
