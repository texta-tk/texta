from celery.result import allow_join_result
from texta_tools.text_splitter import TextSplitter

from toolkit.mlp.tasks import apply_mlp_on_list
from toolkit.settings import CELERY_MLP_TASK_QUEUE
from toolkit.elastic.tools.core import ElasticCore
from elasticsearch.client import IndicesClient
from .exceptions import ElasticSnowballException


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
        self.snowball_filter = {"type": "snowball", "language": language}

    def lemmatize(self, text):
        analyzed_chunks = []
        # split input if token count greater than 5K
        # elastic will complain if token count exceeds 10K
        docs = self.splitter.split(text, max_limit=5000)
        # extract text chunks from docs
        text_chunks = [doc["text"] for doc in docs]
        # analyze text chunks
        for text in text_chunks:
            body = {
                "tokenizer": "standard",
                "text": text,
                "filter": [self.snowball_filter] 
            }
            try:
                analysis = self.indices_client.analyze(body=body)
            except:
                raise ElasticSnowballException("Snowball failed. Check Connection & payload!")
            # tokens back to text chunk
            tokens = [token["token"] for token in analysis["tokens"]]
            token_string = " ".join(tokens)
            analyzed_chunks.append(token_string)
        # return chunks as string
        return " ".join(analyzed_chunks)
