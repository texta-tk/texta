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
        cls.user = create_test_user('embeddingOwner', 'my@email.com', 'pw')
        cls.project = Project.objects.create(
            title='textprocessorTestProject',
            owner=cls.user,
            indices=TEST_INDEX
        )
        cls.user.profile.activate_project(cls.project)
        # Create embedding used in the test
        cls.test_embedding = Embedding.objects.create(
            description='EmbeddingForTesting',
            project=cls.project,
            author=cls.user,
            fields=TEST_FIELD_CHOICE,
            min_freq=1,
            num_dimensions=100,
        )
        # Get the object, since .create does not update on changes
        Embedding.objects.get(id=cls.test_embedding.id)
        cls.test_embedding_id = cls.test_embedding.id


    def test_run(self):
        self.run_cache(W2VEmbedding)
        self.run_cache(Phraser)


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
