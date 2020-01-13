from time import time

from rest_framework.test import APITestCase
from rest_framework import status

from toolkit.test_settings import(TEST_FIELD,
                                  TEST_INDEX_LARGE,
                                  TEST_FIELD_CHOICE,
                                  TEST_FACT_NAME,
                                  TEST_VERSION_PREFIX)
from toolkit.core.project.models import Project
from toolkit.tools.utils_for_tests import create_test_user, print_output, remove_file
from toolkit.neurotagger import choices


class NeurotaggerPerformanceTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        # Owner of the project
        cls.user = create_test_user('neurotaggerOwner', 'my@email.com', 'pw')
        cls.user.is_superuser = True
        cls.user.save()
        cls.project = Project.objects.create(
            title='neurotaggerTestProject',
            indices=TEST_INDEX_LARGE
        )
        cls.url = f'{TEST_VERSION_PREFIX}/projects/{cls.project.id}/neurotaggers/'

    def setUp(self):
        self.client.login(username='neurotaggerOwner', password='pw')

    def test_neurotagger_training_duration(self):
        print('Training Neurotagger')
        payload = {
            "description": "TestNeurotaggerView",
            "fact_name": TEST_FACT_NAME,
            "model_architecture": choices.model_arch_choices[0][0],
            "fields": TEST_FIELD_CHOICE,
        }
        start_time = time()
        response = self.client.post(self.url, payload, format='json')
        print_output('test_neurotagger_training_duration:response.data', response.data)
        # Check if Neurotagger gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        duration = time()-start_time
        print_output('test_neurotagger_training_duration:duration', duration)
