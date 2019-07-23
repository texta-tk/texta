from django.test import TestCase
from toolkit.tools.text_processor import TextProcessor, StopWords
from toolkit.embedding.phraser import Phraser
from toolkit.core.project.models import Project
from toolkit.embedding.models import Embedding
from toolkit.test_settings import TEST_FIELD, TEST_INDEX, TEST_FIELD_CHOICE
from toolkit.tools.utils_for_tests import create_test_user, print_output, remove_file


class TextProcessorTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        # Owner of the project
        cls.user = create_test_user('embeddingOwner', 'my@email.com', 'pw')
        cls.project = Project.objects.create(
            title='textprocessorTestProject',
            owner=cls.user,
            indices=TEST_INDEX
        )
        cls.user.profile.activate_project(cls.project)
        # Create embedding used for the phraser
        cls.test_embedding = Embedding.objects.create(
            description='EmbeddingForTesting',
            project=cls.project,
            author=cls.user,
            fields=TEST_FIELD_CHOICE,
            min_freq=1,
            num_dimensions=100,
        )
        # Get the object, since .create does not update on changes
        cls.test_embedding = Embedding.objects.get(id=cls.test_embedding.id)
        cls.phraser = Phraser(cls.test_embedding.id)
        cls.phraser.load()



    def setUp(self):
        self.client.login(username='embeddingOwner', password='pw')


    def test_run(self):
        self.run_phrase()
        self.run_stop_word_remove()
        self.run_stop_word_remove_custom_stop_words()
        self.run_text_processor()


    def run_phrase(self):
        '''Tests phrasing using Phraser class.'''
        test_text = 'eks olema huvitav , et nii palju rõhk siin oma maine siga'
        # test phrasing with string
        result = self.phraser.phrase(test_text)
        print_output('test_phraser_string:result', result)
        self.assertTrue(isinstance(result, str))
        # test phrasing with list of tokens
        result = self.phraser.phrase(test_text.split(' '))
        print_output('test_phraser_list:result', result)
        self.assertTrue(isinstance(result, list))


    def run_stop_word_remove(self):
        '''Tests removing stopwords using StopWords class'''
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
        '''Tests removing stopwords using StopWords class and list of custom stopwords'''
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
        '''Tests TextProcessor class'''
        test_text = 'eks olema huvitav \n\n et nii palju rõhk siin oma maine siga'
        for phraser_opt in (None, self.phraser):
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