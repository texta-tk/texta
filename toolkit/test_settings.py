"""Settings for unit tests"""
import os

from .settings import TEST_DATA_DIR


TEST_INDEX = "texta_test_index"
TEST_DOCTYPE = "texta_test_index"
TEST_INDEX_REINDEX = f"{TEST_INDEX}_reindexed"
TEST_INDEX_LARGE = "texta_test_index_large"
REINDEXER_TEST_INDEX = "reindexer_test_index"
TEST_FIELD = "comment_content_lemmas"
TEST_FIELD_CHOICE = [TEST_FIELD]
TEST_FIELD_UNLEMMATIZED = "comment_content"
TEST_FIELD_UNLEMMATIZED_CHOICE = [TEST_FIELD_UNLEMMATIZED]
TEST_INTEGER_FIELD = "client_ip"
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

TEST_UAA_USERNAME = 'test1'
TEST_UAA_PASSWORD = 'test1'

# The port for APILiveServerTestCase
# Made this env-readable to make it easier to run tests in a Docker build.
TEST_LIVE_SERVER_PORT = int(os.getenv("TEXTA_TEST_LIVE_SERVER_PORT", 8000))

# Keep plot files created during tests
TEST_KEEP_PLOT_FILES = True if os.getenv("TEXTA_TEST_KEEP_PLOT_FILES", "false").lower() == "true" else False
