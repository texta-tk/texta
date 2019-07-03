from django.test import TestCase
from toolkit.elastic.aggregator import ElasticAggregator
from toolkit.test_settings import TEST_FIELD, TEST_INDEX, TEST_FIELD_CHOICE, TEST_FACT_NAME
from toolkit.utils.utils_for_tests import create_test_user, print_output, remove_file


class TestElasticAggregator(TestCase):

    def test_run(self):
        self.run_update_field_data()
        self.run_facts()


    def run_update_field_data(self):
        '''Tests ElasticAggregator field data update.'''
        elastic_aggregator = ElasticAggregator()
        decoded_field_data = elastic_aggregator.core.decode_field_data(TEST_FIELD_CHOICE)
        elastic_aggregator.update_field_data([decoded_field_data])
        self.assertTrue(elastic_aggregator.field_data)      


    def run_facts(self):
        '''Tests ElasticAggregator fact retrieval.'''
        # test without defining index.
        elastic_aggregator = ElasticAggregator()
        facts = elastic_aggregator.facts()
        print_output('test_run_facts:facts', facts)
        self.assertTrue(isinstance(facts, dict))
        self.assertTrue(len(list(facts.keys())) > 0)
        # test with test index
        elastic_aggregator = ElasticAggregator(indices=[TEST_INDEX])
        facts = elastic_aggregator.facts()
        print_output('test_run_facts_with_index:facts', facts)
        self.assertTrue(isinstance(facts, dict))
        self.assertTrue(len(list(facts.keys())) > 0)
        self.assertTrue(TEST_FACT_NAME in facts)
        # test with field data
        decoded_field_data = elastic_aggregator.core.decode_field_data(TEST_FIELD_CHOICE)
        elastic_aggregator = ElasticAggregator(field_data=[decoded_field_data])
        facts = elastic_aggregator.facts()
        print_output('test_run_facts_with_field_data:facts', facts)
        self.assertTrue(isinstance(facts, dict))
        self.assertTrue(len(list(facts.keys())) > 0)
        self.assertTrue(TEST_FACT_NAME in facts)
