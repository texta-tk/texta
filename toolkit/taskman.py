import os

from celery import Celery

from toolkit.base_task import BaseTask


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'toolkit.settings')
app = Celery('taskman')

# Using a string here means the worker will not have to
# pickle the object when using Windows.
app.config_from_object('django.conf:settings')
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))


class MlpTask(BaseTask):
    ignore_result = False
    name = "MlpTask"

    _mlp = None


    @property
    def mlp(self):
        from texta_mlp.mlp import MLP
        from toolkit.settings import DEFAULT_MLP_LANGUAGE_CODES, MLP_MODEL_DIRECTORY

        if self._mlp is None:
            self._mlp = MLP(
                language_codes=DEFAULT_MLP_LANGUAGE_CODES,
                default_language_code="et",
                resource_dir=MLP_MODEL_DIRECTORY,
                logging_level="info"
            )

        return self._mlp


    def run(self, list_or_doc: str, *args, **kwargs):
        if list_or_doc == "doc":
            response = self.mlp.process_docs(docs=kwargs["docs"], analyzers=kwargs["analyzers"], doc_paths=kwargs["fields_to_parse"])
            return response

        elif list_or_doc == "list":
            response = []
            for text in kwargs["texts"]:
                analyzed_text = self.mlp.process(text, kwargs["analyzers"])
                response.append(analyzed_text)
            return response


mlp_task = MlpTask()
app.register_task(mlp_task)
