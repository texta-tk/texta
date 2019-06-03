from django.db.models import signals

from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.test import APIClient

from toolkit.core.project.models import Project
from toolkit.tagger.models import Tagger
from toolkit.core.task.models import Task
from toolkit.utils.utils_for_tests import create_test_user
# Third party Factory Boy for testing
# import factory

class TaggerViewTests(APITestCase):
    def setUp(self):
        # Owner of the project
        self.user = create_test_user('owner', 'my@email.com', 'pw')
        self.project = Project.objects.create(
            title='testproj',
            owner=self.user,
            indices="delfi_comments_for_tests"
        )

        self.user.profile.activate_project(self.project)
        self.client = APIClient()
        self.client.login(username='owner', password='pw')

        # self.test_tagger = Tagger.objects.create(
        #     description='TaggerForTesting',
        #     project=self.project,
        #     author=self.user,
        #     vectorizer = 0,
        #     classifier = 0,
        #     # fields='kysimus_ja_vastus',
        # )

        self.url = f'/taggers/'
    
    # @factory.django.mute_signals(signals.post_save)
    def test_create_tagger_training_and_task_signal(self):
        '''Tests the endpoint for a new Tagger, and if a new Task gets created via the signal'''
        # TODO Move the testing configuration, like fields/index to a separate file, test_settings or something
        payload = {
            "description": "TestTagger",
            "query": "",
            "fields": "index=delfi_comments_for_tests&mapping=data&field_path=comment_content_lemmas&field_type=text",
            #"embedding": None,
            "vectorizer": 0,
            "classifier": 0,
            "maximum_sample_size": 500,
            "negative_multiplier": "1.0",
        }
        
        response = self.client.post(self.url, payload)
        print(response.data)
        # Check if Tagger gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_tagger = Tagger.objects.get(id=response.data['id'])
        # Check if Task gets created via a signal
        self.assertTrue(created_tagger.task is not None)
        # Check the Tagger gets trained and completed
        self.assertEqual(created_tagger.task.status, Task.STATUS_COMPLETED)


    # def test_tag_text(self):
    #     '''Tests the endpoint for the tag_text action'''
    #     payload = { "text": "This is some test text for the Tagger Test" }
    #     tag_text_url = f'{self.url}{self.test_tagger.id}/tag_text/'
    #     response = self.client.post(tag_text_url, payload)
    #     self.assertEqual(response.status_code, status.HTTP_200_OK)
    #     # Check if response data is not empty, but a result instead
    #     self.assertTrue(response.data)
