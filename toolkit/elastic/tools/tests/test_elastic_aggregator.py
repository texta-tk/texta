from django.test import TestCase

from toolkit.elastic.tools.aggregator import ElasticAggregator
from toolkit.helper_functions import reindex_test_dataset
from toolkit.test_settings import TEST_FACT_NAME, TEST_FIELD_CHOICE
from toolkit.tools.utils_for_tests import print_output


class TestElasticAggregator(TestCase):

    def setUp(self):
        self.test_index_name = reindex_test_dataset()


    def tearDown(self) -> None:
        from toolkit.elastic.tools.core import ElasticCore
        ElasticCore().delete_index(index=self.test_index_name, ignore=[400, 404])


    def test_run(self):
        self.run_update_field_data()
        self.run_facts()


    def run_update_field_data(self):
        """Tests ElasticAggregator field data update."""
        elastic_aggregator = ElasticAggregator()
        elastic_aggregator.update_field_data(TEST_FIELD_CHOICE)
        self.assertTrue(elastic_aggregator.field_data)


    def run_facts(self):
        """Tests ElasticAggregator fact retrieval."""

        # test with test index
        elastic_aggregator = ElasticAggregator(indices=[self.test_index_name])
        facts = elastic_aggregator.facts()
        print_output('test_run_facts_with_index:facts', facts)
        self.assertTrue(isinstance(facts, dict))
        self.assertTrue(len(list(facts.keys())) > 0)
        self.assertTrue(TEST_FACT_NAME in facts)
        # test with field data
        elastic_aggregator = ElasticAggregator(field_data=TEST_FIELD_CHOICE, indices=[self.test_index_name])
        facts = elastic_aggregator.facts()
        print_output('test_run_facts_with_field_data:facts', facts)
        self.assertTrue(isinstance(facts, dict))
        self.assertTrue(len(list(facts.keys())) > 0)
        self.assertTrue(TEST_FACT_NAME in facts)
