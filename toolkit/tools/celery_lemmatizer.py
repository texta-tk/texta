from celery.result import allow_join_result

from toolkit.mlp.tasks import apply_mlp_on_list
from toolkit.settings import CELERY_MLP_TASK_QUEUE


class CeleryLemmatizer:

    def __init__(self):
        pass
    
    def lemmatize(self, text):
        with allow_join_result():
            mlp = apply_mlp_on_list.apply_async(kwargs={"texts": [text], "analyzers": ["lemmas"]}, queue=CELERY_MLP_TASK_QUEUE).get()
            lemmas = mlp[0]["text"]["lemmas"]
            return lemmas
