from django.test import TestCase
from toolkit.elastic.tools.aggregator import ElasticAggregator
from toolkit.test_settings import TEST_FIELD, TEST_INDEX, TEST_FIELD_CHOICE, TEST_FACT_NAME
from toolkit.tools.utils_for_tests import create_test_user, print_output, remove_file


class TestElasticAggregator(TestCase):

    def test_run(self):
        self.run_update_field_data()
        self.run_facts()

    def run_update_field_data(self):
        '''Tests ElasticAggregator field data update.'''
        elastic_aggregator = ElasticAggregator()
        elastic_aggregator.update_field_data(TEST_FIELD_CHOICE)
        self.assertTrue(elastic_aggregator.field_data)

    def run_facts(self):
        '''Tests ElasticAggregator fact retrieval.'''

        # test with test index
        elastic_aggregator = ElasticAggregator(indices=[TEST_INDEX])
        facts = elastic_aggregator.facts()
        print_output('test_run_facts_with_index:facts', facts)
        self.assertTrue(isinstance(facts, dict))
        self.assertTrue(len(list(facts.keys())) > 0)
        self.assertTrue(TEST_FACT_NAME in facts)
        # test with field data
        elastic_aggregator = ElasticAggregator(field_data=TEST_FIELD_CHOICE, indices=[TEST_INDEX])
        facts = elastic_aggregator.facts()
        print_output('test_run_facts_with_field_data:facts', facts)
        self.assertTrue(isinstance(facts, dict))
        self.assertTrue(len(list(facts.keys())) > 0)
        self.assertTrue(TEST_FACT_NAME in facts)
