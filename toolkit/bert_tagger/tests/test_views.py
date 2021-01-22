import pathlib
from io import BytesIO
from time import sleep

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITransactionTestCase

from toolkit.test_settings import (
    TEST_FACT_NAME,
    TEST_FIELD_CHOICE,
    TEST_INDEX,
    TEST_VERSION_PREFIX,
    TEST_KEEP_PLOT_FILES,
    TEST_BERT_MODEL
    )
from toolkit.tools.utils_for_tests import create_test_user, print_output, project_creation, remove_file
from toolkit.bert_tagger.models import BertTagger


@override_settings(CELERY_ALWAYS_EAGER=True)
class BertTaggerViewTests(APITransactionTestCase):
    def setUp(self):
        # Owner of the project
        self.user = create_test_user('BertTaggerOwner', 'my@email.com', 'pw')
        self.project = project_creation("BertTaggerTestProject", TEST_INDEX, self.user)
        self.project.users.add(self.user)
        self.url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/bert_taggers/'
        self.project_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}'
        self.test_embedding_id = None
        self.test_tagger_id = None

        self.client.login(username='BertTaggerOwner', password='pw')


    def test(self):
        self.run_train_bert_tagger_using_query()
        self.run_train_multiclass_bert_tagger_using_fact_name()
        self.run_bert_tag_text()
        self.run_bert_tag_random_doc()
        self.run_bert_epoch_reports_get()
        self.run_bert_epoch_reports_post()
        self.run_bert_tag_and_feedback_and_retrain()
        self.run_bert_model_export_import()

    def add_cleanup_files(self, tagger_id):
        tagger_object = BertTagger.objects.get(pk=tagger_id)
        self.addCleanup(remove_file, tagger_object.model.path)
        if not TEST_KEEP_PLOT_FILES:
            self.addCleanup(remove_file, tagger_object.plot.path)

    def run_train_bert_tagger_using_query(self):
        """Tests BertTagger training, and if a new Task gets created via the signal"""
        payload = {
            "description": "TestBertTaggerTraining",
            "fields": TEST_FIELD_CHOICE,
            "maximum_sample_size": 500,
            "indices": [{"name": TEST_INDEX}],
            "num_epochs": 2,
            "bert_model": TEST_BERT_MODEL
        }

        print_output(f"training tagger with payload: {payload}", 200)
        response = self.client.post(self.url, payload, format='json')
        print_output('test_create_binary_bert_tagger_training_and_task_signal:response.data', response.data)

        # Check if BertTagger gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Check if f1 not NULL (train and validation success)
        tagger_id = response.data['id']
        response = self.client.get(f'{self.url}{tagger_id}/')
        print_output('test_bert_tagger_has_stats:response.data', response.data)
        for score in ['f1_score', 'precision', 'recall', 'accuracy']:
            self.assertTrue(isinstance(response.data[score], float))
        self.test_tagger_id = tagger_id
        # add cleanup
        self.add_cleanup_files(tagger_id)


    def run_train_multiclass_bert_tagger_using_fact_name(self):
        """Tests BertTagger training with multiple classes and if a new Task gets created via the signal"""
        payload = {
            "description": "TestBertTaggerTraining",
            "fact_name": TEST_FACT_NAME,
            "fields": TEST_FIELD_CHOICE,
            "indices": [{"name": TEST_INDEX}],
            "maximum_sample_size": 500,
            "num_epochs": 2,
            "bert_model": TEST_BERT_MODEL
        }
        response = self.client.post(self.url, payload, format='json')
        print_output('test_create_multiclass_bert_tagger_training_and_task_signal:response.data', response.data)
        # Check if BertTagger gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Check if f1 not NULL (train and validation success)
        tagger_id = response.data['id']
        response = self.client.get(f'{self.url}{tagger_id}/')
        print_output('test_bert_tagger_has_stats:response.data', response.data)
        for score in ['f1_score', 'precision', 'recall', 'accuracy']:
            self.assertTrue(isinstance(response.data[score], float))
        self.test_tagger_id = tagger_id
        # add cleanup
        self.add_cleanup_files(tagger_id)


    def run_bert_tag_text(self):
        """Tests tag prediction for texts."""
        payload = {
            "text": "mine kukele, kala"
        }
        response = self.client.post(f'{self.url}{self.test_tagger_id}/tag_text/', payload)
        print_output('test_bert_tagger_tag_text:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue("probability" in response.data)
        self.assertTrue("result" in response.data)
        self.assertTrue("tagger_id" in response.data)


    def run_bert_tag_random_doc(self):
        """Tests the endpoint for the tag_random_doc action"""
        payload = {
            "indices": [{"name": TEST_INDEX}],
            "fields": TEST_FIELD_CHOICE
        }
        url = f'{self.url}{self.test_tagger_id}/tag_random_doc/'
        response = self.client.post(url, format="json", data=payload)
        print_output('test_bert_tagger_tag_random_doc:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response is a dict
        self.assertTrue(isinstance(response.data, dict))
        self.assertTrue("prediction" in response.data)
        self.assertTrue("document" in response.data)

    def run_bert_epoch_reports_get(self):
        """Tests endpoint for retrieving epoch reports via GET"""
        url = f'{self.url}{self.test_tagger_id}/epoch_reports/'
        response = self.client.get(url, format="json")
        print_output('test_bert_tagger_epoch_reports_get:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response is a list
        self.assertTrue(isinstance(response.data, list))
        # Check if first report is not empty
        self.assertTrue(len(response.data[0])>0)

    def run_bert_epoch_reports_post(self):
        """Tests endpoint for retrieving epoch reports via GET"""
        url = f'{self.url}{self.test_tagger_id}/epoch_reports/'
        payload_1 = {}
        payload_2 = {"ignore_fields": ["true_positive_rate", "false_positive_rate", "recall"]}

        response = self.client.post(url, format="json", data=payload_1)
        print_output('test_bert_tagger_epoch_reports_post_ignore_default:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check if response is a list
        self.assertTrue(isinstance(response.data, list))
        # Check if first report contains recall
        self.assertTrue("recall" in response.data[0])

        response = self.client.post(url, format="json", data=payload_2)
        print_output('test_bert_tagger_epoch_reports_post_ignore_custom:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response is a list
        self.assertTrue(isinstance(response.data, list))
        # Check if first report does NOT contains recall
        self.assertTrue("recall" not in response.data[0])

    def run_bert_model_export_import(self):
        """Tests endpoint for model export and import"""
        test_tagger_id = self.test_tagger_id

        # retrieve model zip
        url = f'{self.url}{test_tagger_id}/export_model/'
        response = self.client.get(url)

        # Post model zip
        import_url = f'{self.url}import_model/'
        response = self.client.post(import_url, data={'file': BytesIO(response.content)})
        print_output('test_bert_import_model:response.data', import_url)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        bert_tagger = BertTagger.objects.get(pk=response.data["id"])

        # Check if the models and plot files exist.
        resources = bert_tagger.get_resource_paths()
        for path in resources.values():
            file = pathlib.Path(path)
            self.assertTrue(file.exists())

        # Tests the endpoint for the tag_random_doc action"""
        url = f'{self.url}{bert_tagger.pk}/tag_random_doc/'
        random_doc_payload = {
            "indices": [{"name": TEST_INDEX}],
            "fields": TEST_FIELD_CHOICE
        }
        response = self.client.post(url, data=random_doc_payload, format="json")
        print_output('test_bert_tag_random_doc_after_model_import:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data, dict))

        self.assertTrue('prediction' in response.data)


    def run_bert_tag_and_feedback_and_retrain(self):
        """Tests feeback extra action."""
        tagger_id = self.test_tagger_id
        payload = {
            "text": "This is some test text for the Tagger Test",
            "feedback_enabled": True
        }
        tag_text_url = f'{self.url}{tagger_id}/tag_text/'
        response = self.client.post(tag_text_url, payload)
        print_output('test_bert_tag_text_with_feedback:response.data', response.data)
        self.assertTrue('feedback' in response.data)

        # generate feedback
        fb_id = response.data['feedback']['id']
        feedback_url = f'{self.url}{tagger_id}/feedback/'
        payload = {"feedback_id": fb_id, "correct_result": "FUBAR"}
        response = self.client.post(feedback_url, payload, format='json')
        print_output('test_bert_tag_text_feedback:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data)
        self.assertTrue('success' in response.data)
        # sleep for a sec to allow elastic to finish its bussiness
        sleep(1)
        # list feedback
        feedback_list_url = f'{self.url}{tagger_id}/feedback/'
        response = self.client.get(feedback_list_url)
        print_output('test_tag_text_list_feedback:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data)
        self.assertTrue(len(response.data) > 0)

        # add model files before retraining
        self.add_cleanup_files(tagger_id)

        # retrain model
        url = f'{self.url}{tagger_id}/retrain_tagger/'
        response = self.client.post(url)
        print_output('test_bert_tagger_feedback:retrain', response.data)
        # test tagging again for this model
        payload = {"text": "This is some test text for the Tagger Test"}
        tag_text_url = f'{self.url}{tagger_id}/tag_text/'
        response = self.client.post(tag_text_url, payload)
        print_output('test_bert_tagger_feedback_retrained_tag_doc:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue('result' in response.data)
        self.assertTrue('probability' in response.data)
        # delete feedback
        feedback_delete_url = f'{self.url}{tagger_id}/feedback/'
        response = self.client.delete(feedback_delete_url)
        print_output('test_bert_tagger_tag_doc_delete_feedback:response.data', response.data)
        # sleep for a sec to allow elastic to finish its bussiness
        sleep(1)
        # list feedback again to make sure its emtpy
        feedback_list_url = f'{self.url}{tagger_id}/feedback/'
        response = self.client.get(feedback_list_url)
        print_output('test_bert_tagger_tag_doc_list_feedback_after_delete:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(len(response.data) == 0)
        # remove created index
        feedback_index_url = f'{self.project_url}/feedback/'
        response = self.client.delete(feedback_index_url)
        print_output('test_bert_tagger_delete_feedback_index:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue('success' in response.data)

        # add model files after retraining
        self.add_cleanup_files(tagger_id)
