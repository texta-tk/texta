from django.test import TestCase
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.test_settings import TEST_FIELD, TEST_INDEX, TEST_FIELD_CHOICE
from toolkit.utils.utils_for_tests import create_test_user, print_output, remove_file


class TestElasticSearcher(TestCase):

    def test_run(self):
        self.run_update_field_data()
        self.run_count()
        self.run_search()
       # self.run_iterator()


    def run_update_field_data(self):
        '''Tests ElasticSearcher field data update.'''
        elastic_searcher = ElasticSearcher()
        decoded_field_data = elastic_searcher.core.decode_field_data(TEST_FIELD_CHOICE)
        elastic_searcher.update_field_data([decoded_field_data])
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
        field_data = [ElasticSearcher().core.decode_field_data(TEST_FIELD_CHOICE)]
        # test without field data & indices
        elastic_searcher = ElasticSearcher()
        result = elastic_searcher.search(size=1)
        print_output('test_run_search:result', result)
        self.assertTrue(isinstance(result, list))
        self.assertTrue(result[0])     
        # test with field data
        elastic_searcher = ElasticSearcher(field_data=field_data)
        result = elastic_searcher.search(size=1)
        print_output('test_run_search_with_field_data:result', result)
        self.assertTrue(isinstance(result, list))
        self.assertTrue(TEST_FIELD in result[0])
        # test with index list
        elastic_searcher = ElasticSearcher(indices=[TEST_INDEX])
        result = elastic_searcher.search(size=1)
        print_output('test_run_search_with_index_list:result', result)    
        self.assertTrue(isinstance(result, list))
        self.assertTrue(TEST_FIELD in result[0])


    def run_iterator(self):
        '''Tests ElasticSearcher scrolling as iterator.'''
        field_data = ElasticSearcher().core.decode_field_data(TEST_FIELD_CHOICE)
        elastic_searcher = ElasticSearcher(field_data=[field_data])
        #for a in elastic_searcher:
        #    print(a)

        #print_output('test_run_search:result', result)     