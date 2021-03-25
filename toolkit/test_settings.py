"""Settings for unit tests"""
import os

from .settings import TEST_DATA_DIR as TEST_DATA_DIR_ROOT

TEST_DATA_DIR = os.path.join(TEST_DATA_DIR_ROOT, "import_test_data")

TEST_INDEX = "texta_test_index"
TEST_DOCTYPE = "texta_test_index"
TEST_INDEX_REINDEX = f"{TEST_INDEX}_reindexed"
TEST_INDEX_LARGE = "texta_test_index_large"
REINDEXER_TEST_INDEX = "reindexer_test_index"

REINDEXER_VALIDATION_TEST_INDEX_1 = "test_*_index"
REINDEXER_VALIDATION_TEST_INDEX_2 = "test_:_index"
REINDEXER_VALIDATION_TEST_INDEX_3 = "test_#_index"
REINDEXER_VALIDATION_TEST_INDEX_4 = "test_ _index"
REINDEXER_VALIDATION_TEST_INDEX_5 = "-test_new_index"
REINDEXER_VALIDATION_TEST_INDEX_6 = "Test_new_index"

INDEX_SPLITTING_TEST_INDEX = "splitting_test"
INDEX_SPLITTING_TRAIN_INDEX = "splitting_train"

TEST_FIELD = "comment_content_lemmas"
TEST_FIELD_CHOICE = [TEST_FIELD]
TEST_FIELD_UNLEMMATIZED = "comment_content"
TEST_FIELD_UNLEMMATIZED_CHOICE = [TEST_FIELD_UNLEMMATIZED]
TEST_INTEGER_FIELD = "client_ip"
TEST_FACT_NAME = "TEEMA"
TEST_MATCH_TEXT = "loll"
TEST_QUERY = {"query": {"match": {TEST_FIELD: {"query": TEST_MATCH_TEXT}}}}
TEST_EMPTY_QUERY = {"query": {"match_all": {}}}

TEST_DATASETS = (
    os.path.join(TEST_DATA_DIR, "import_test_data.csv"),
    os.path.join(TEST_DATA_DIR, "import_test_data.xls"),
    os.path.join(TEST_DATA_DIR, "import_test_data.xlsx"),
)
TEST_IMPORT_DATASET = "texta-test-import-dataset"
VERSION_NAMESPACE = "v1"
TEST_VERSION_PREFIX = f"/api/{VERSION_NAMESPACE}"

TEST_UAA_USERNAME = 'test1'
TEST_UAA_PASSWORD = 'test1'

TEST_IMAGE_FILE_1 = os.path.join(TEST_DATA_DIR, "photos", "test_image_1.jpg")
TEST_IMAGE_FILE_2 = os.path.join(TEST_DATA_DIR, "photos", "test_image_2.jpg")

# Test BERT models trained on GPU
TEST_BERT_TAGGER_BINARY_GPU = os.path.join(TEST_DATA_DIR, "models", "bert_tagger", "gpu", "berttagger_model_41.zip")
TEST_BERT_TAGGER_MULTICLASS_GPU = os.path.join(TEST_DATA_DIR, "models", "bert_tagger", "gpu", "berttagger_model_42.zip")

# Test BERT model trained on CPU
TEST_BERT_TAGGER_BINARY_CPU = os.path.join(TEST_DATA_DIR, "models", "bert_tagger", "cpu", "berttagger_model_1.zip")

# Test Torch models trained on GPU
TEST_TORCH_TAGGER_BINARY_GPU = os.path.join(TEST_DATA_DIR, "models", "torch_tagger", "gpu", "torchtagger_model_12.zip")
TEST_TORCH_TAGGER_MULTICLASS_GPU = os.path.join(TEST_DATA_DIR, "models", "torch_tagger", "gpu", "torchtagger_model_13.zip")

# Test Torch model trained on CPU
TEST_TORCH_TAGGER_BINARY_CPU = os.path.join(TEST_DATA_DIR, "models", "torch_tagger", "cpu", "torchtagger_model_1.zip")

TEST_TAGGER_BINARY = os.path.join(TEST_DATA_DIR, "models", "tagger", "tagger_model_35.zip")
TEST_TAGGER_MULTICLASS = os.path.join(TEST_DATA_DIR, "models", "tagger", "tagger_model_36.zip")

TEST_TAGGER_GROUP = os.path.join(TEST_DATA_DIR, "models", "tagger_group", "tagger_group_5.zip")

# The port for APILiveServerTestCase
# Made this env-readable to make it easier to run tests in a Docker build.
TEST_LIVE_SERVER_PORT = int(os.getenv("TEXTA_TEST_LIVE_SERVER_PORT", 8000))

# Keep plot files created during tests
TEST_KEEP_PLOT_FILES = True if os.getenv("TEXTA_TEST_KEEP_PLOT_FILES", "false").lower() == "true" else False

TEST_BERT_MODEL = "prajjwal1/bert-tiny"
W2V_EMBEDDING = "W2VEmbedding"
FASTTEXT_EMBEDDING = "FastTextEmbedding"

TEST_FACE_ANALYZER_INDEX = "test_face_analyzer_index"
