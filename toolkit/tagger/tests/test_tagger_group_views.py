import json
import pathlib
from io import BytesIO

from rest_framework import status
from rest_framework.test import APITestCase

from toolkit.core.project.models import Project
from toolkit.core.task.models import Task
from toolkit.tagger.models import Tagger, TaggerGroup
from toolkit.test_settings import (TEST_FACT_NAME,
                                   TEST_FIELD,
                                   TEST_FIELD_CHOICE,
                                   TEST_INDEX,
                                   TEST_VERSION_PREFIX)
from toolkit.tools.utils_for_tests import create_test_user, print_output, remove_file


class TaggerGroupViewTests(APITestCase):

    @classmethod
    def setUpTestData(cls):
        # Owner of the project
        cls.user = create_test_user('taggerOwner', 'my@email.com', 'pw')
        # cls.user.is_superuser = True
        # cls.user.save()
        cls.project = Project.objects.create(
            title='taggerGroupTestProject',
            indices=TEST_INDEX
        )
        cls.project.users.add(cls.user)
        cls.url = f'{TEST_VERSION_PREFIX}/projects/{cls.project.id}/tagger_groups/'
        cls.test_tagger_group_id = None


    def setUp(self):
        self.client.login(username='taggerOwner', password='pw')


    def test_run(self):
        self.run_create_and_delete_tagger_group_removes_related_children_models_plots()
        self.run_create_tagger_group_training_and_task_signal()
        self.run_tag_text()
        self.run_tag_doc()
        self.run_tag_random_doc()
        self.run_models_retrain()
        self.create_taggers_with_empty_fields()
        self.run_model_export_import()


    def run_create_tagger_group_training_and_task_signal(self):
        '''Tests the endpoint for a new Tagger Group, and if a new Task gets created via the signal'''
        payload = {
            "description": "TestTaggerGroup",
            "minimum_sample_size": 50,
            "fact_name": TEST_FACT_NAME,
            "tagger": {
                "fields": TEST_FIELD_CHOICE,
                "vectorizer": "Hashing Vectorizer",
                "classifier": "LinearSVC",
                "feature_selector": "SVM Feature Selector",
                "maximum_sample_size": 500,
                "negative_multiplier": 1.0
            }
        }
        response = self.client.post(self.url, payload, format='json')
        print_output('test_create_tagger_group_training_and_task_signal:response.data', response.data)
        # Check if TaggerGroup gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # add tagger to be tested
        created_tagger_group = TaggerGroup.objects.get(id=response.data['id'])
        self.test_tagger_group_id = created_tagger_group.pk

        for tagger in created_tagger_group.taggers.all():
            # run this for each tagger in tagger group
            # Remove tagger files after test is done
            self.addCleanup(remove_file, tagger.model.path)
            self.addCleanup(remove_file, tagger.plot.path)
            # Check if not errors
            self.assertEqual(tagger.task.errors, '[]')
            # Check if Task gets created via a signal
            self.assertTrue(tagger.task is not None)
            # Check if Tagger gets trained and completed
            self.assertEqual(tagger.task.status, Task.STATUS_COMPLETED)


    def create_taggers_with_empty_fields(self):
        payload = {
            "description": "TestTaggerGroup",
            "minimum_sample_size": 50,
            "fact_name": TEST_FACT_NAME,
            "tagger": {
                "fields": [],
                "vectorizer": "Hashing Vectorizer",
                "classifier": "LinearSVC",
                "feature_selector": "SVM Feature Selector",
                "maximum_sample_size": 500,
                "negative_multiplier": 1.0,
            }
        }
        response = self.client.post(self.url, payload, format='json')
        print_output('create_taggers_with_empty_fields:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


    def run_tag_text(self):
        '''Tests the endpoint for the tag_text action'''
        payload = {"text": "see on mingi suvaline naisteka kommentaar. ehk joppab ja saab täägi"}
        tag_text_url = f'{self.url}{self.test_tagger_group_id}/tag_text/'
        response = self.client.post(tag_text_url, payload)
        print_output('test_tag_text_group:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response is list
        self.assertTrue(isinstance(response.data, list))


    def run_tag_doc(self):
        '''Tests the endpoint for the tag_doc action'''
        payload = {"doc": json.dumps({TEST_FIELD: "This is some test text for the Tagger Test"})}
        url = f'{self.url}{self.test_tagger_group_id}/tag_doc/'
        response = self.client.post(url, payload)
        print_output('test_tag_doc_group:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response is list
        self.assertTrue(isinstance(response.data, list))


    def run_tag_random_doc(self):
        '''Tests the endpoint for the tag_random_doc action'''
        url = f'{self.url}{self.test_tagger_group_id}/tag_random_doc/'
        response = self.client.get(url)
        print_output('test_tag_random_doc_group:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response is list
        self.assertTrue(isinstance(response.data, dict))
        self.assertTrue('tags' in response.data)


    def run_models_retrain(self):
        '''Tests the endpoint for the models_retrain action'''
        url = f'{self.url}{self.test_tagger_group_id}/models_retrain/'
        response = self.client.post(url)
        print_output('test_models_retrain:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response data
        self.assertTrue(response.data)
        self.assertTrue('success' in response.data)
        # remove retrained tagger models
        retrained_tagger_group = TaggerGroup.objects.get(id=response.data['tagger_group_id'])
        for tagger in retrained_tagger_group.taggers.all():
            self.addCleanup(remove_file, tagger.model.path)
            self.addCleanup(remove_file, tagger.plot.path)


    def run_create_and_delete_tagger_group_removes_related_children_models_plots(self):
        payload = {
            "description": "TestTaggerGroup",
            "minimum_sample_size": 50,
            "fact_name": TEST_FACT_NAME,
            "tagger": {
                "fields": TEST_FIELD_CHOICE,
                "vectorizer": "Hashing Vectorizer",
                "classifier": "LinearSVC",
                "feature_selector": "SVM Feature Selector",
                "maximum_sample_size": 500,
                "negative_multiplier": 1.0,
            }
        }

        # Create a tagger_group.
        create_response = self.client.post(self.url, payload, format='json')
        tagger_group_url = create_response.data["url"]
        tagger_group_id = create_response.data["id"]
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        tagger_group = TaggerGroup.objects.get(id=tagger_group_id)
        child_taggers = tagger_group.taggers.all()

        # Check if there are more than one Taggers created as expected.
        self.assertEqual(child_taggers.count() > 1, True)

        # Check if files were created.
        for tagger in child_taggers:
            has_plot_file = pathlib.Path(tagger.plot.path).exists()
            has_model_file = pathlib.Path(tagger.model.path).exists()
            self.assertEqual(has_model_file, True)
            self.assertEqual(has_plot_file, True)

        # Delete the TaggerGroup
        self.client.delete(tagger_group_url)

        # Because it has a ManyToMany with no CASCADE, check if the child Taggers are gone.
        tagger_ids = [tagger.id for tagger in child_taggers]
        tagger_count = Tagger.objects.filter(id__in=tagger_ids).count()
        self.assertEqual(tagger_count == 0, True)

        # Check whether the files are deleted.
        for tagger in child_taggers:
            has_plot_file = pathlib.Path(tagger.plot.path).exists()
            has_model_file = pathlib.Path(tagger.model.path).exists()
            self.assertEqual(has_model_file, False)
            self.assertEqual(has_plot_file, False)


    def run_model_export_import(self):
        """Tests endpoint for model export and import"""
        test_tagger_group_id = self.test_tagger_group_id

        # retrieve model zip
        url = f'{self.url}{test_tagger_group_id}/export_model/'
        response = self.client.get(url)

        # Post model zip
        import_url = f'{self.url}import_model/'
        response = self.client.post(import_url, data={'file': BytesIO(response.content)})
        print_output('test_import_model:response.data', import_url)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        tg = TaggerGroup.objects.get(pk=response.data["id"])

        self.assertTrue(tg.taggers.count() > 1)

        # Check if the models and plot files exist.
        resources = tg.get_resource_paths()
        for item in resources:
            for path in item.values():
                file = pathlib.Path(path)
                self.assertTrue(file.exists())

        # Tests the endpoint for the tag_random_doc action'''
        url = f'{self.url}{tg.pk}/tag_random_doc/'
        response = self.client.get(url)
        print_output('test_tag_random_doc_group:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data, dict))
        self.assertTrue('tags' in response.data)
