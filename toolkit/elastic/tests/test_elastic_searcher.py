from django.test import TestCase
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.test_settings import TEST_FIELD, TEST_INDEX, TEST_FIELD_CHOICE
from toolkit.tools.utils_for_tests import print_output


class TestElasticSearcher(TestCase):

    def test_run(self):
        self.run_update_field_data()
        self.run_count()
        self.run_search()
        self.run_iterator()
        self.run_count_with_nonexisting_index()

    def run_update_field_data(self):
        '''Tests ElasticSearcher field data update.'''
        elastic_searcher = ElasticSearcher()
        elastic_searcher.update_field_data(TEST_FIELD_CHOICE)
        self.assertTrue(elastic_searcher.field_data)

    def run_count(self):
        '''Tests ElasticSearcher count method.'''
        elastic_searcher = ElasticSearcher()
        count = elastic_searcher.count()
        print_output('test_run_count:count', count)
        self.assertTrue(isinstance(count, int))
        self.assertTrue(count > 0)

    def run_search(self):
        '''Tests ElasticSearcher search method.'''
        elastic_searcher = ElasticSearcher(indices=[TEST_INDEX], field_data=TEST_FIELD_CHOICE)
        result = elastic_searcher.search(size=1)
        print_output('test_run_searchresult', result)
        self.assertTrue(isinstance(result, list))
        self.assertTrue(TEST_FIELD in result[0])

    def run_iterator(self):
        '''Tests ElasticSearcher scrolling as iterator.'''
        elastic_searcher = ElasticSearcher(indices=[TEST_INDEX], field_data=TEST_FIELD_CHOICE)
        i = 0
        last_hit = None
        for hit in elastic_searcher:
            i += 1
            if i >= 500:
                last_hit = hit
                break
        print_output('test_run_search_iterator:last_hit', last_hit)
        self.assertTrue(isinstance(last_hit, dict))
        self.assertTrue(TEST_FIELD in last_hit)

    def run_count_with_nonexisting_index(self):
        '''Tests ElasticSearcher count method with nonexisting index.'''
        elastic_searcher = ElasticSearcher(indices=['asdasdasd'])
        count = elastic_searcher.count()
        print_output('test_run_count_nonexiting_index:count', count)
        self.assertTrue(isinstance(count, int))
        self.assertTrue(count == 0)
