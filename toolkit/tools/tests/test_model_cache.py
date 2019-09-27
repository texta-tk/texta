from django.test import TestCase
from toolkit.tools.model_cache import ModelCache
from toolkit.embedding.models import Embedding
from toolkit.embedding.phraser import Phraser
from toolkit.core.project.models import Project
from toolkit.embedding.embedding import W2VEmbedding
from toolkit.tools.utils_for_tests import create_test_user, print_output
from toolkit.test_settings import TEST_INDEX, TEST_FIELD_CHOICE
from time import sleep


class TestModelCache(TestCase):

    @classmethod
    def setUpTestData(cls):
        # Owner of the project
        cls.user = create_test_user('modelCacheOwner', 'my@email.com', 'pw')
        cls.project = Project.objects.create(
            title='textprocessorTestProject',
            owner=cls.user,
            indices=TEST_INDEX
        )
        cls.test_embedding_id = None


    def setUp(self):
        self.client.login(username='modelCacheOwner', password='pw')


    def test_run(self):
        self.run_train_embedding()
        self.run_cache(W2VEmbedding)
        self.run_cache(Phraser)
    

    def run_train_embedding(self):
        # payload for training embedding
        payload = {
            "description": "TestEmbedding",
            "query": "",
            "fields": TEST_FIELD_CHOICE,
            "max_vocab": 10000,
            "min_freq": 5,
            "num_dimensions": 100,
        }
        # post
        embeddings_url = f'/projects/{self.project.id}/embeddings/'
        response = self.client.post(embeddings_url, payload, format='json')
        self.test_embedding_id = response.data["id"]


    def run_cache(self, model_class):
        '''Tests ModelCache with any model class.'''
        # create model cache with timeout of 1 second
        model_cache = ModelCache(model_class, cache_duration=1)
        # check if model cache empty at initialization
        self.assertTrue(isinstance(model_cache.models, dict))
        self.assertTrue(not model_cache.models)
        # load model to cache
        model_cache.get_model(self.test_embedding_id)
        print_output('test_run_cache_with_embedding:models', model_cache.models)
        # check if model present in the cache
        self.assertTrue(isinstance(model_cache.models, dict))
        self.assertTrue(model_cache.models)
        self.assertTrue(self.test_embedding_id in model_cache.models)
        # sleep for 1 second to wait for model cache timeout
        sleep(1)
        # try cleaning the cache
        model_cache.clean_cache()
        print_output('test_run_cache_with_embedding_clean_cache:models', model_cache.models)
        # check if model cache empty again
        self.assertTrue(isinstance(model_cache.models, dict))
        self.assertTrue(not model_cache.models)        
