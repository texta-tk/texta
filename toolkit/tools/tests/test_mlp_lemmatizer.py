from celery.result import allow_join_result
from django.test import TestCase, override_settings

from toolkit.mlp.tasks import apply_mlp_on_list
from toolkit.settings import CELERY_MLP_TASK_QUEUE
from toolkit.tools.utils_for_tests import print_output


@override_settings(CELERY_ALWAYS_EAGER=True)
class MLPLemmatizerTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.test_texts = [
            {"lang": "et", "text": "See eestikeelne tekst peab saama lemmatiseeritud!"},
            {"lang": "en", "text": "This text is beyond boring. But its in English!"},
            {"lang": "ru", "text": "Путин обсудил с Совбезом РФ ситуацию в Сирии и ДРСМД"}
        ]


    def test_lemmatization(self):
        """
        Tests lemmatization in every language.
        """
        for test_text in self.test_texts:
            with allow_join_result():
                mlp = apply_mlp_on_list.apply_async(kwargs={"texts": [test_text], "analyzers": ["lemmas"]}, queue=CELERY_MLP_TASK_QUEUE).get()
            lemmas = mlp[0]["text"]["lemmas"]

            print_output(f"test_mlp_lemmatization_{test_text['lang']}:result", lemmas)
            self.assertTrue(len(lemmas) > 0)
