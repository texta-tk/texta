import json

from django.test import TransactionTestCase, override_settings

from toolkit.tools.utils_for_tests import project_creation
from toolkit.tools.text_processor import TextProcessor, StopWords
from toolkit.embedding.phraser import Phraser
from toolkit.core.project.models import Project
from toolkit.embedding.models import Embedding
from toolkit.test_settings import TEST_INDEX, TEST_FIELD_CHOICE, TEST_VERSION_PREFIX
from toolkit.tools.utils_for_tests import create_test_user, print_output


@override_settings(CELERY_ALWAYS_EAGER=True)
class TextProcessorTests(TransactionTestCase):

    def setUp(self):
        # Owner of the project
        self.user = create_test_user('textProcessorOwner', 'my@email.com', 'pw')
        self.user.is_superuser = True
        self.user.save()
        self.project = project_creation("textprocessorTestProject", TEST_INDEX, self.user)


        self.test_embedding = None
        self.test_phraser = None

        self.client.login(username='textProcessorOwner', password='pw')


    def test_run(self):
        self.run_train_embedding()
        self.run_phrase()
        self.run_stop_word_remove()
        self.run_stop_word_remove_custom_stop_words()
        self.run_text_processor()


    def tearDown(self) -> None:
        Embedding.objects.all().delete()


    def run_train_embedding(self):
        # payload for training embedding
        payload = {
            "description": "TestEmbedding",
            "fields": TEST_FIELD_CHOICE,
            "max_vocab": 10000,
            "min_freq": 5,
            "num_dimensions": 100,
        }
        # post
        embeddings_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/embeddings/'
        response = self.client.post(embeddings_url, json.dumps(payload), content_type='application/json')
        # load embedding & phraser
        self.test_embedding = Embedding.objects.get(id=response.data['id'])
        self.test_phraser = Phraser(self.test_embedding.id)
        self.test_phraser.load()


    def run_phrase(self):
        """Tests phrasing using Phraser class."""
        test_text = 'eks olema huvitav , et nii palju rõhk siin oma maine siga'
        # test phrasing with string
        result = self.test_phraser.phrase(test_text)
        print_output('test_phraser_string:result', result)
        self.assertTrue(isinstance(result, str))
        # test phrasing with list of tokens
        result = self.test_phraser.phrase(test_text.split(' '))
        print_output('test_phraser_list:result', result)
        self.assertTrue(isinstance(result, list))


    def run_stop_word_remove(self):
        """Tests removing stopwords using StopWords class"""
        test_text = 'eks olema huvitav , et nii palju rõhk siin oma maine siga'
        # test stop word removal with string
        result = StopWords().remove(test_text)
        print_output('test_stop_word_removal_string:result', result)
        self.assertTrue(isinstance(result, str))
        self.assertTrue('olema' not in result)
        # test stop word removal with list of tokens
        result = StopWords().remove(test_text.split(' '))
        print_output('test_stop_word_removal_list:result', result)
        self.assertTrue(isinstance(result, list))
        self.assertTrue('olema' not in result)


    def run_stop_word_remove_custom_stop_words(self):
        """Tests removing stopwords using StopWords class and list of custom stopwords"""
        test_text = 'eks olema huvitav , et nii palju rõhk siin oma maine siga'
        custom_stop_words = ['siga', 'maine']
        # test stop word removal with string
        result = StopWords(custom_stop_words=custom_stop_words).remove(test_text)
        print_output('test_stop_word_removal_custom_stop_words_string:result', result)
        self.assertTrue(isinstance(result, str))
        self.assertTrue('siga' not in result)
        # test stop word removal with list of tokens
        result = StopWords(custom_stop_words=custom_stop_words).remove(test_text.split(' '))
        print_output('test_stop_word_removal_custom_stop_words_list:result', result)
        self.assertTrue(isinstance(result, list))
        self.assertTrue('siga' not in result)


    def run_text_processor(self):
        """Tests TextProcessor class"""
        test_text = 'eks olema huvitav \n\n et nii palju rõhk siin oma maine siga'
        for phraser_opt in (None, self.test_phraser):
            tp = TextProcessor(phraser=phraser_opt)
            result = tp.process(test_text)
            print_output('test_text_processor_phraser:result', result)
            self.assertTrue(isinstance(result, list))
            self.assertTrue(isinstance(result[0], str))

        # test with stop word removal
        tp = TextProcessor(remove_stop_words=True)
        result = tp.process(test_text)
        print_output('test_text_processor_with_stop_words:result', result)
        self.assertTrue(isinstance(result, list))
        self.assertTrue('olema' not in result)

        # test without stop word removal
        tp = TextProcessor(remove_stop_words=False)
        result = tp.process(test_text)
        print_output('test_text_processor_without_stop_words:result', result)
        self.assertTrue(isinstance(result, list))
        self.assertTrue('olema' in result[0])

        # test with sentence splitting
        tp = TextProcessor(sentences=True)
        result = tp.process(test_text)
        print_output('test_text_processor_sentences:result', result)
        self.assertTrue(isinstance(result, list))
        self.assertTrue(len(result) > 1)

        # test with tokenization & sentence splitting & without stop word removal
        tp = TextProcessor(sentences=True, tokenize=True, remove_stop_words=False)
        result = tp.process(test_text)
        print_output('test_text_processor_sentences:result', result)
        self.assertTrue(isinstance(result, list))
        self.assertTrue(len(result) > 1)
        self.assertTrue(len(result[1]) > 1 and isinstance(result[1][0], str))
