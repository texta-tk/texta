'''Settings for unit tests'''

TEST_INDEX = 'texta_test_index'
TEST_INDEX_REINDEX = f'{TEST_INDEX}_reindexed'
TEST_FIELD_CHOICE = ["comment_content_lemmas"]
TEST_FIELD = 'comment_content_lemmas'
TEST_FACT_NAME = 'TEEMA'
TEST_QUERY = {"query": {"bool": {"should": [], "must": [], "must_not": []}}}
