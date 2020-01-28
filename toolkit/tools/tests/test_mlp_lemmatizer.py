from django.test import TestCase
from toolkit.tools.mlp_analyzer import MLPAnalyzer
from toolkit.tools.utils_for_tests import print_output


class MLPLemmatizerTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.lemmatizer = MLPAnalyzer()
        cls.test_texts = [
            {"lang": "et", "text": "See eestikeelne tekst peab saama lemmatiseeritud!"},
            {"lang": "en", "text": "This text is beyond boring. But its in English!"},
            {"lang": "ru", "text": "Путин обсудил с Совбезом РФ ситуацию в Сирии и ДРСМД"}
        ]
    
    def test_status_and_version_check(self):
        """
        Tests MLP service health and version.
        """
        status = self.lemmatizer.status
        print_output("test_mlp_status:status", status)
        self.assertTrue(status)
        version = self.lemmatizer.version     
        print_output("test_mlp_version:version", version)
        self.assertTrue(version > 0)  

    def test_lemmatization(self):
        """
        Tests lemmatization in every language.
        """
        for test_text in self.test_texts:
            result = self.lemmatizer.lemmatize(test_text["text"])
            print_output(f"test_mlp_lemmatization_{test_text['lang']}:result", result)
            self.assertTrue(len(result) > 0)
