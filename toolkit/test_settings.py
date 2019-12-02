'''Settings for unit tests'''

TEST_INDEX = "texta_test_index"
TEST_INDEX_REINDEX = f'{TEST_INDEX}_reindexed'
TEST_INDEX_LARGE = "texta_test_index_large"
TEST_FIELD_CHOICE = ["comment_content_lemmas"]
TEST_FIELD = "comment_content_lemmas"
TEST_FACT_NAME = "TEEMA"
TEST_MATCH_TEXT = "loll"
TEST_QUERY = {"query": {"match": {TEST_FIELD: {"query": TEST_MATCH_TEXT}}}}

TEST_DATASETS = ["/home/rsirel/dev/texta-rest/data/erakonnad_25_01_2019.csv", 
#"/home/rsirel/dev/texta-rest/data/import.xlsx"
]
TEST_IMPORT_DATASET = "texta-test-import-dataset"