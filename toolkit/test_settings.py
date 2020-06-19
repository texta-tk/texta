"""Settings for unit tests"""
import os

from .settings import TEST_DATA_DIR


TEST_INDEX = "texta_test_index"
TEST_DOCTYPE = "texta_test_index"
TEST_INDEX_REINDEX = f"{TEST_INDEX}_reindexed"
TEST_INDEX_LARGE = "texta_test_index_large"
REINDEXER_TEST_INDEX = "reindexer_test_index"
TEST_FIELD_CHOICE = ["comment_content_lemmas"]
TEST_FIELD = "comment_content_lemmas"
TEST_FACT_NAME = "TEEMA"
TEST_MATCH_TEXT = "loll"
TEST_QUERY = {"query": {"match": {TEST_FIELD: {"query": TEST_MATCH_TEXT}}}}

TEST_DATASETS = (
    os.path.join(TEST_DATA_DIR, "import_test_data.csv"),
    os.path.join(TEST_DATA_DIR, "import_test_data.xls"),
    os.path.join(TEST_DATA_DIR, "import_test_data.xlsx"),
)
TEST_IMPORT_DATASET = "texta-test-import-dataset"
TEST_VERSION_PREFIX = "/api/v1"
