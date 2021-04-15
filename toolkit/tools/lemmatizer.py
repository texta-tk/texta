import logging
from typing import Optional

import elasticsearch
from celery.result import allow_join_result
from elasticsearch.client import IndicesClient
from texta_tools.text_splitter import TextSplitter

from toolkit.elastic.tools.core import ElasticCore
from toolkit.mlp.tasks import apply_mlp_on_list
from toolkit.settings import CELERY_MLP_TASK_QUEUE, ERROR_LOGGER


class CeleryLemmatizer:

    def __init__(self):
        pass


    def lemmatize(self, text):
        with allow_join_result():
            mlp = apply_mlp_on_list.apply_async(kwargs={"texts": [text], "analyzers": ["lemmas"]}, queue=CELERY_MLP_TASK_QUEUE).get()
            lemmas = mlp[0]["text"]["lemmas"]
            return lemmas


class ElasticLemmatizer:

    def __init__(self, language="english"):
        self.core = ElasticCore()
        self.indices_client = IndicesClient(self.core.es)
        self.splitter = TextSplitter(split_by="WORD_LIMIT")
        self.language = language


    def lemmatize(self, text: str, language: Optional[str] = None) -> str:
        analyzed_chunks = []
        # Split input if token count greater than 5K.
        # Elastic will complain if token count exceeds 10K.
        docs = self.splitter.split(text, max_limit=5000)
        # Extract text chunks from docs.
        text_chunks = [doc["text"] for doc in docs]
        # Analyze text chunks.

        # This line is for allowing stemming based on the language in the document.
        # Creating the class for every object would be a waste of resources so instead this
        # workaround allows for both while not breaking existing code.
        lang = self.language if language is None else language
        for text in text_chunks:
            body = {
                "tokenizer": "standard",
                "text": text,
                "filter": [{"type": "snowball", "language": lang}]
            }
            try:
                analysis = self.indices_client.analyze(body=body)
                tokens = [token["token"] for token in analysis["tokens"]]
                token_string = " ".join(tokens)
                analyzed_chunks.append(token_string)
            except elasticsearch.exceptions.RequestError as e:
                reason = e.info["error"]["reason"]
                if "Invalid stemmer class" in reason:
                    logging.getLogger(ERROR_LOGGER).warning(e)
                else:
                    logging.getLogger(ERROR_LOGGER).exception(e)
            except Exception as e:
                logging.getLogger(ERROR_LOGGER).exception(e)

        # Return chunks as string.
        return " ".join(analyzed_chunks)
