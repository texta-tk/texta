from celery.result import allow_join_result

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
        self.snowball_filter = {"type": "snowball", "language": language}

    def lemmatize(self, text):
        body = {
            "tokenizer": "standard",
            "text": text,
            "filter": [self.snowball_filter]
            
        }
        try:
            analysis = self.indices_client.analyze(body=body)
        except:
            raise ElasticSnowballException("Snowball failed. Check Connection & payload!")

        tokens = [token["token"] for token in analysis["tokens"]]
        token_string = " ".join(tokens)

        return token_string
