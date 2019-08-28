import json
import os
from django.db.models import signals

from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.test import APIClient

from toolkit.test_settings import TEST_FIELD, TEST_INDEX, TEST_FIELD_CHOICE, TEST_FACT_NAME
from toolkit.core.project.models import Project
from toolkit.neurotagger.models import Neurotagger
from toolkit.core.task.models import Task
from toolkit.tools.utils_for_tests import create_test_user, print_output, remove_file
from toolkit.neurotagger import choices
from toolkit.elastic.searcher import EMPTY_QUERY



class NeurotaggerViewTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        # Owner of the project
        cls.user = create_test_user('neurotaggerOwner', 'my@email.com', 'pw')

        cls.project = Project.objects.create(
            title='neurotaggerTestProject',
            owner=cls.user,
            indices=TEST_INDEX
        )

        cls.url = f'/projects/{cls.project.id}/neurotaggers/'
        cls.test_neurotagger = Neurotagger.objects.create(
            queries=json.dumps([EMPTY_QUERY]),
            query_names=json.dumps(["First query"]),
            description='NeurotaggerForTesting',
            model_architecture=choices.model_arch_choices[0][0],
            project=cls.project,
            author=cls.user,
            fields=json.dumps(TEST_FIELD_CHOICE),
            maximum_sample_size=500,
        )
        # Get the object, since .create does not update on changes
        cls.test_neurotagger = Neurotagger.objects.get(id=cls.test_neurotagger.id)


    def setUp(self):
        self.client.login(username='neurotaggerOwner', password='pw')


    def test_run(self):
        self.run_create_neurotagger_training_and_task_signal()
        self.run_create_and_tag_multilabel()
        self.run_tag_doc()
        self.run_tag_text()


    def run_create_neurotagger_training_and_task_signal(self):
        '''Tests the endpoint for a new Neurotagger, and if a new Task gets created via the signal'''
        payload = {
            "queries": json.dumps([EMPTY_QUERY]),
            "description": "TestNeurotagger",
            "model_architecture": choices.model_arch_choices[0][0],
            "fields": TEST_FIELD_CHOICE,
            "maximum_sample_size": 500,
        }
        response = self.client.post(self.url, payload, format='json')
        print_output('test_create_neurotagger_training_and_task_signal:response.data', response.data)
        # Check if Neurotagger gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_neurotagger = Neurotagger.objects.get(id=response.data['id'])

        # Remove neurotagger files after test is done
        if 'model' in created_neurotagger.location:
            self.addCleanup(remove_file, json.loads(created_neurotagger.location)['model'])
        if 'tokenizer_model' in created_neurotagger.location:
            self.addCleanup(remove_file, json.loads(created_neurotagger.location)['tokenizer_model'])
            self.addCleanup(remove_file, json.loads(created_neurotagger.location)['tokenizer_vocab'])

        if created_neurotagger.plot:
            remove_file(created_neurotagger.plot.path)
        if created_neurotagger.model_plot:
            remove_file(created_neurotagger.model_plot.path)

        # Check if Task gets created via a signal
        self.assertTrue(created_neurotagger.task is not None)
        if created_neurotagger.task.errors:
            print_output('test_create_neurotagger_training_and_task_signal:task.errors', created_neurotagger.task.errors)
            
        # Check if Neurotagger gets trained and completed
        self.assertEqual(created_neurotagger.task.status, Task.STATUS_COMPLETED)


    def run_create_and_tag_multilabel(self):
        '''Tests the endpoint for a new multilabel Neurotagger with facts, and if a new Task gets created via the signal'''
        payload = {
            "description": "TestNeurotagger",
            "fact_name": TEST_FACT_NAME,
            "model_architecture": choices.model_arch_choices[0][0],
            "fields": TEST_FIELD_CHOICE,
            "maximum_sample_size": 500,
        }
        response = self.client.post(self.url, payload, format='json')
        print_output('test_create_neurotagger_training_and_task_signal:response.data', response.data)
        # Check if Neurotagger gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_neurotagger = Neurotagger.objects.get(id=response.data['id'])

        # Test the tagging endpoints 
        self.run_tag_text(tagger_id=created_neurotagger.id)
        self.run_tag_doc(tagger_id=created_neurotagger.id)
        
        # Remove neurotagger files after test is done
        if 'model' in created_neurotagger.location:
            self.addCleanup(remove_file, json.loads(created_neurotagger.location)['model'])
        if 'tokenizer_model' in created_neurotagger.location:
            self.addCleanup(remove_file, json.loads(created_neurotagger.location)['tokenizer_model'])
            self.addCleanup(remove_file, json.loads(created_neurotagger.location)['tokenizer_vocab'])
            

        if created_neurotagger.plot:
            remove_file(created_neurotagger.plot.path)
        if created_neurotagger.model_plot:
            remove_file(created_neurotagger.model_plot.path)

        # Check if Task gets created via a signal
        self.assertTrue(created_neurotagger.task is not None)
        if created_neurotagger.task.errors:
            print_output('test_create_neurotagger_training_and_task_signal:task.errors', created_neurotagger.task.errors)
            
        # Check if Neurotagger gets trained and completed
        self.assertEqual(created_neurotagger.task.status, Task.STATUS_COMPLETED)


    def run_tag_text(self, tagger_id=None):
        '''Tests the endpoint for the tag_text action'''
        if not tagger_id:
            tagger_id = self.test_neurotagger.id
        payload = { "text": "This is some test text for the Tagger Test" }
        tag_text_url = f'{self.url}{tagger_id}/tag_text/'
        response = self.client.post(tag_text_url, payload)
        print_output('test_tag_text:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response data is not empty, but a result instead
        self.assertTrue(response.data)
        self.assertTrue('classes' in response.data)
        self.assertTrue('probability' in response.data)


    def run_tag_doc(self, tagger_id=None):
        '''Tests the endpoint for the tag_doc action'''
        if not tagger_id:
            tagger_id = self.test_neurotagger.id

        payload = { "doc": json.dumps({TEST_FIELD: "This is some test text for the Tagger Test" })}
        tag_text_url = f'{self.url}{tagger_id}/tag_doc/'
        response = self.client.post(tag_text_url, payload)
        print_output('test_tag_doc:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response data is not empty, but a result instead
        self.assertTrue(response.data)
        self.assertTrue('classes' in response.data)
        self.assertTrue('probability' in response.data)


    @classmethod
    def tearDownClass(cls):
        if 'model' in cls.test_neurotagger.location:
            remove_file(json.loads(cls.test_neurotagger.location)['model'])
        if 'tokenizer_model' in cls.test_neurotagger.location:
            remove_file(json.loads(cls.test_neurotagger.location)['tokenizer_model'])
        if 'tokenizer_vocab' in cls.test_neurotagger.location:
            remove_file(json.loads(cls.test_neurotagger.location)['tokenizer_vocab'])

        if cls.test_neurotagger.plot:
            remove_file(cls.test_neurotagger.plot.path)
        if cls.test_neurotagger.model_plot:
            remove_file(cls.test_neurotagger.model_plot.path)
