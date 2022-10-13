import json
from time import sleep

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITransactionTestCase
from texta_elastic.aggregator import ElasticAggregator
from texta_elastic.core import ElasticCore
from texta_elastic.searcher import ElasticSearcher

from toolkit.core.task.models import Task
from toolkit.elastic.index.models import Index
from toolkit.elastic.index_splitter.models import IndexSplitter
from toolkit.helper_functions import reindex_test_dataset
from toolkit.test_settings import (INDEX_SPLITTING_TEST_INDEX, INDEX_SPLITTING_TRAIN_INDEX, TEST_INDEX_OBJECT_FIELD, TEST_QUERY, TEST_VERSION_PREFIX)
from toolkit.tools.utils_for_tests import create_test_user, print_output, project_creation


@override_settings(CELERY_ALWAYS_EAGER=True)
class IndexSplitterViewTests(APITransactionTestCase):
    def setUp(self):
        """ User needs to be admin, because of changed indices permissions. """
        self.test_index_name = reindex_test_dataset()
        self.default_password = 'pw'
        self.default_username = 'indexOwner'
        self.user = create_test_user(self.default_username, 'my@email.com', self.default_password)

        self.admin = create_test_user(name='admin', password='1234')
        self.admin.is_superuser = True
        self.admin.save()
        self.project = project_creation("IndexSplittingTestProject", self.test_index_name, self.user)
        self.project.users.add(self.user)

        self.url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/elastic/index_splitter/'

        self.client.login(username=self.default_username, password=self.default_password)
        self.ec = ElasticCore()
        self.FACT = "TEEMA"


    def test_create_splitter_object_and_task_signal(self):
        payload = {
            "description": "Random index splitting",
            "indices": [{"name": self.test_index_name}],
            "train_index": INDEX_SPLITTING_TRAIN_INDEX,
            "test_index": INDEX_SPLITTING_TEST_INDEX,
            "distribution": "random",
            "test_size": 20
        }

        response = self.client.post(self.url, json.dumps(payload), content_type='application/json')

        print_output('test_create_splitter_object_and_task_signal:response.data', response.data)

        splitter_obj = IndexSplitter.objects.get(id=response.data['id'])
        print_output("indices:", splitter_obj.get_indices())
        # Check if IndexSplitter object gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Check if Task gets created
        task_object = splitter_obj.tasks.last()
        self.assertTrue(task_object is not None)
        print_output("status of IndexSplitter's Task object", task_object.status)
        # Check if Task gets completed
        self.assertEqual(task_object.status, Task.STATUS_COMPLETED)

        sleep(5)

        original_count = ElasticSearcher(indices=self.test_index_name).count()
        test_count = ElasticSearcher(indices=INDEX_SPLITTING_TEST_INDEX).count()
        train_count = ElasticSearcher(indices=INDEX_SPLITTING_TRAIN_INDEX).count()

        print_output('original_count, test_count, train_count', [original_count, test_count, train_count])

        # Test that usernames are added automatically into the newly created index.
        self.assertTrue(Index.objects.filter(name=INDEX_SPLITTING_TEST_INDEX, added_by=self.user.username).exists())
        self.assertTrue(Index.objects.filter(name=INDEX_SPLITTING_TRAIN_INDEX, added_by=self.user.username).exists())


    def test_create_random_split(self):
        payload = {
            "description": "Random index splitting",
            "indices": [{"name": self.test_index_name}],
            "train_index": INDEX_SPLITTING_TRAIN_INDEX,
            "test_index": INDEX_SPLITTING_TEST_INDEX,
            "distribution": "random",
            "test_size": 20
        }

        response = self.client.post(self.url, data=payload)
        print_output('test_create_random_split:response.data', response.data)

        splitter_obj = IndexSplitter.objects.get(id=response.data['id'])

        # Assert Task gets completed
        self.assertEqual(Task.STATUS_COMPLETED, Task.STATUS_COMPLETED)
        print_output("Task status", Task.STATUS_COMPLETED)

        sleep(5)

        original_count = ElasticSearcher(indices=self.test_index_name).count()
        test_count = ElasticSearcher(indices=INDEX_SPLITTING_TEST_INDEX).count()
        train_count = ElasticSearcher(indices=INDEX_SPLITTING_TRAIN_INDEX).count()

        print_output('original_count, test_count, train_count', [original_count, test_count, train_count])
        # To avoid any inconsistencies caused by rounding assume sizes are between small limits
        self.assertTrue(self.is_between_limits(test_count, original_count, 0.2))
        self.assertTrue(self.is_between_limits(train_count, original_count, 0.8))


    def test_create_original_split(self):
        payload = {
            "description": "Original index splitting",
            "indices": [{"name": self.test_index_name}],
            "train_index": INDEX_SPLITTING_TRAIN_INDEX,
            "test_index": INDEX_SPLITTING_TEST_INDEX,
            "distribution": "original",
            "test_size": 20,
            "fact": self.FACT
        }

        response = self.client.post(self.url, data=payload)
        print_output('test_create_original_split:response.data', response.data)

        splitter_obj = IndexSplitter.objects.get(id=response.data['id'])

        # Assert Task gets completed
        self.assertEqual(Task.STATUS_COMPLETED, Task.STATUS_COMPLETED)
        print_output("Task status", Task.STATUS_COMPLETED)

        sleep(5)

        original_distribution = ElasticAggregator(indices=self.test_index_name).get_fact_values_distribution(self.FACT)
        test_distribution = ElasticAggregator(indices=INDEX_SPLITTING_TEST_INDEX).get_fact_values_distribution(self.FACT)
        train_distribution = ElasticAggregator(indices=INDEX_SPLITTING_TRAIN_INDEX).get_fact_values_distribution(self.FACT)

        print_output('original_dist, test_dist, train_dist', [original_distribution, test_distribution, train_distribution])

        for label, quant in original_distribution.items():
            self.assertTrue(self.is_between_limits(test_distribution[label], quant, 0.2))
            self.assertTrue(self.is_between_limits(train_distribution[label], quant, 0.8))


    def test_create_equal_split(self):
        payload = {
            "description": "Original index splitting",
            "indices": [{"name": self.test_index_name}],
            "train_index": INDEX_SPLITTING_TRAIN_INDEX,
            "test_index": INDEX_SPLITTING_TEST_INDEX,
            "distribution": "equal",
            "test_size": 20,
            "fact": self.FACT
        }

        response = self.client.post(self.url, data=payload)
        print_output('test_create_equal_split:response.data', response.data)

        splitter_obj = IndexSplitter.objects.get(id=response.data['id'])

        # Assert Task gets completed
        self.assertEqual(Task.STATUS_COMPLETED, Task.STATUS_COMPLETED)
        print_output("Task status", Task.STATUS_COMPLETED)

        sleep(5)

        original_distribution = ElasticAggregator(indices=self.test_index_name).get_fact_values_distribution(self.FACT)
        test_distribution = ElasticAggregator(indices=INDEX_SPLITTING_TEST_INDEX).get_fact_values_distribution(self.FACT)
        train_distribution = ElasticAggregator(indices=INDEX_SPLITTING_TRAIN_INDEX).get_fact_values_distribution(self.FACT)

        print_output('original_dist, test_dist, train_dist', [original_distribution, test_distribution, train_distribution])

        for label, quant in original_distribution.items():
            if (quant > 20):
                self.assertEqual(test_distribution[label], 20)
                self.assertEqual(train_distribution[label], quant - 20)
            else:
                self.assertEqual(test_distribution[label], quant)
                self.assertTrue(label not in train_distribution)


    def test_create_custom_split(self):
        custom_distribution = {"FUBAR": 10, "bar": 15}
        payload = {
            "description": "Original index splitting",
            "indices": [{"name": self.test_index_name}],
            "train_index": INDEX_SPLITTING_TRAIN_INDEX,
            "test_index": INDEX_SPLITTING_TEST_INDEX,
            "distribution": "custom",
            "fact": self.FACT,
            "custom_distribution": json.dumps(custom_distribution)
        }

        response = self.client.post(self.url, data=payload, format="json")
        print_output('test_create_custom_split:response.data', response.data)

        splitter_obj = IndexSplitter.objects.get(id=response.data['id'])

        # Assert Task gets completed
        self.assertEqual(Task.STATUS_COMPLETED, Task.STATUS_COMPLETED)
        print_output("Task status", Task.STATUS_COMPLETED)

        sleep(5)

        original_distribution = ElasticAggregator(indices=self.test_index_name).get_fact_values_distribution(self.FACT)
        test_distribution = ElasticAggregator(indices=INDEX_SPLITTING_TEST_INDEX).get_fact_values_distribution(self.FACT)
        train_distribution = ElasticAggregator(indices=INDEX_SPLITTING_TRAIN_INDEX).get_fact_values_distribution(self.FACT)

        print_output('original_dist, test_dist, train_dist', [original_distribution, test_distribution, train_distribution])

        for label, quant in custom_distribution.items():
            self.assertEqual(test_distribution[label], min(quant, original_distribution[label]))

        for label in original_distribution.keys():
            if label not in custom_distribution:
                self.assertTrue(label not in test_distribution)
                self.assertTrue(original_distribution[label], train_distribution[label])


    def test_create_original_split_fact_value_given(self):
        payload = {
            "description": "Original index splitting",
            "indices": [{"name": self.test_index_name}],
            "train_index": INDEX_SPLITTING_TRAIN_INDEX,
            "test_index": INDEX_SPLITTING_TEST_INDEX,
            "distribution": "original",
            "test_size": 20,
            "fact": self.FACT,
            "str_val": "FUBAR"
        }

        response = self.client.post(self.url, data=payload, format="json")
        print_output('test_create_original_split_fact_value_given:response.data', response.data)

        splitter_obj = IndexSplitter.objects.get(id=response.data['id'])

        sleep(5)

        original_distribution = ElasticAggregator(indices=self.test_index_name).get_fact_values_distribution(self.FACT)
        test_distribution = ElasticAggregator(indices=INDEX_SPLITTING_TEST_INDEX).get_fact_values_distribution(self.FACT)
        train_distribution = ElasticAggregator(indices=INDEX_SPLITTING_TRAIN_INDEX).get_fact_values_distribution(self.FACT)

        print_output('original_dist, test_dist, train_dist', [original_distribution, test_distribution, train_distribution])

        for label, quant in original_distribution.items():
            if label == "FUBAR":
                self.assertTrue(self.is_between_limits(test_distribution[label], quant, 0.2))
                self.assertTrue(self.is_between_limits(train_distribution[label], quant, 0.8))


    def test_query_given(self):
        payload = {
            "description": "Original index splitting",
            "indices": [{"name": self.test_index_name}],
            "train_index": INDEX_SPLITTING_TRAIN_INDEX,
            "test_index": INDEX_SPLITTING_TEST_INDEX,
            "distribution": "original",
            "test_size": 20,
            "fact": self.FACT,
            "str_val": "bar",
            "query": json.dumps(TEST_QUERY)
        }

        response = self.client.post(self.url, data=payload, format="json")
        print_output('test_query_given:response.data', response.data)

        original_distribution = ElasticAggregator(indices=self.test_index_name).get_fact_values_distribution(self.FACT)
        test_distribution = ElasticAggregator(indices=INDEX_SPLITTING_TEST_INDEX).get_fact_values_distribution(self.FACT)
        train_distribution = ElasticAggregator(indices=INDEX_SPLITTING_TRAIN_INDEX).get_fact_values_distribution(self.FACT)

        print_output('original_dist, test_dist, train_dist', [original_distribution, test_distribution, train_distribution])

        self.assertTrue("bar" in test_distribution)
        self.assertTrue("bar" in train_distribution)
        self.assertTrue("foo" not in train_distribution and "foo" not in test_distribution)
        self.assertTrue("FUBAR" not in train_distribution and "FUBAR" not in test_distribution)


    def tearDown(self):
        self.ec.delete_index(index=self.test_index_name, ignore=[400, 404])
        res = self.ec.delete_index(INDEX_SPLITTING_TEST_INDEX)
        print_output('attempt to delete test index:', res)
        res = self.ec.delete_index(INDEX_SPLITTING_TRAIN_INDEX)
        print_output('attempt to delete train index:', res)


    def is_between_limits(self, value, base, ratio):
        return value <= base * ratio + 1 and value >= base * ratio - 1


    # There used to be a bug in which objects were flattened in the split index unintentionally.
    def test_that_split_index_with_nested_field_still_has_nested_field(self):
        payload = {
            "description": "Random index splitting",
            "indices": [{"name": self.test_index_name}],
            "train_index": INDEX_SPLITTING_TRAIN_INDEX,
            "test_index": INDEX_SPLITTING_TEST_INDEX,
            "distribution": "random",
            "test_size": 20
        }

        response = self.client.post(self.url, data=payload, format="json")
        print_output('test_that_split_index_with_nested_field_still_has_nested_field:response.data', response.data)
        at_least_once = False
        es = ElasticSearcher(indices=[INDEX_SPLITTING_TEST_INDEX, INDEX_SPLITTING_TEST_INDEX], field_data=[TEST_INDEX_OBJECT_FIELD], flatten=False)
        for item in es:
            data = item.get(TEST_INDEX_OBJECT_FIELD, None)
            if data:
                self.assertTrue(isinstance(data, dict))
                at_least_once = True
        self.assertTrue(at_least_once)
