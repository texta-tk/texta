import logging
import os
import pathlib
import warnings
from datetime import timedelta

import environ
from corsheaders.defaults import default_headers
from kombu import Exchange, Queue

from .helper_functions import download_bert_requirements, download_mlp_requirements, download_nltk_resources, parse_bool_env, parse_list_env_headers, parse_tuple_env_headers, \
    prepare_mandatory_directories, validate_aes_file
from .logging_settings import setup_logging

# Ignore Python Warning base class
warnings.simplefilter(action="ignore", category=Warning)

env_file_path = os.getenv("TEXTA_ENV_FILE", None)
if env_file_path:
    import termcolor

    termcolor.cprint(f"Loading env file: {env_file_path}!", color="green")
    environ.Env.read_env(env_file=env_file_path)

env = environ.Env()

# Used in cases where multiple Toolkit instances share resources like Elasticsearch or DB.
# Helps differentiate them when creating static index names.
DEPLOY_KEY = env.int("TEXTA_DEPLOY_KEY", default=1)

# Used as the folder name in project folders for search exports.
SEARCHER_FOLDER_KEY = "searcher"

# Names of Celery queues.
CELERY_LONG_TERM_TASK_QUEUE = "long_term_tasks"
CELERY_SHORT_TERM_TASK_QUEUE = "short_term_tasks"
CELERY_MLP_TASK_QUEUE = "mlp_queue"
CELERY_LONG_TERM_GPU_TASK_QUEUE = "long_term_gpu_tasks"

### CORE SETTINGS ###
# NOTE: THESE ARE INITIAL VARIABLES IMPORTED FROM THE ENVIRONMENT
# DO NOT IMPORT THESE VARIABLES IN APPS, BECAUSE THEY CAN BE OVERWRITTEN WITH VALUES FROM DB
# INSTEAD USE get_setting_val() function, e.g.:
# from toolkit.helper_functions import get_core_setting
# ES_URL = get_core_setting("ES_URL")

PROTECTED_CORE_KEYS = ("SECRET", "KEY", "PASSWORD")

CORE_SETTINGS = {
    "TEXTA_ES_URL": env("TEXTA_ES_URL", default="http://localhost:9200"),
    "TEXTA_ES_PREFIX": env("TEXTA_ES_PREFIX", default=""),
    "TEXTA_ES_USERNAME": env("TEXTA_ES_USER", default=""),
    "TEXTA_ES_PASSWORD": env("TEXTA_ES_PASSWORD", default=""),
    "TEXTA_EVALUATOR_MEMORY_BUFFER_GB": env("TEXTA_EVALUATOR_MEMORY_BUFFER_GB", default=""),
    "TEXTA_ES_MAX_DOCS_PER_INDEX": env.int("TEXTA_ES_MAX_DOCS_PER_INDEX", default=100000),
    # Default is set to long term task-queue to be backwards compatible.
    "TEXTA_LONG_TERM_GPU_TASK_QUEUE": env("TEXTA_LONG_TERM_GPU_TASK_QUEUE", default=CELERY_LONG_TERM_TASK_QUEUE),

    ### S3 CONFIGURATION ###
    "TEXTA_S3_ENABLED": env.bool("TEXTA_S3_ENABLED", default=False),
    "TEXTA_S3_USE_SECURE": env.bool("TEXTA_S3_USE_SECURE", default=False),
    "TEXTA_S3_HOST": env.str("TEXTA_S3_HOST", default=""),
    "TEXTA_S3_BUCKET_NAME": env.str("TEXTA_S3_BUCKET_NAME", default=""),
    "TEXTA_S3_ACCESS_KEY": env.str("TEXTA_S3_ACCESS_KEY", default=""),
    "TEXTA_S3_SECRET_KEY": env.str("TEXTA_S3_SECRET_KEY", default=""),
}
### END OF CORE SETTINGS ###

AES_KEY_ENV = "TEXTA_AES_KEY_FILE_PATH"
AES_KEYFILE_PATH = env.str(AES_KEY_ENV, default="secret.key")
validate_aes_file(AES_KEYFILE_PATH, AES_KEY_ENV)

EVALUATOR_MEMORY_BUFFER_RATIO = 0.5

TEXTA_TAGS_KEY = "texta_facts"
TEXTA_ANNOTATOR_KEY = "texta_annotator"

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("TEXTA_SECRET_KEY", default="eqr9sjz-&baah&c%ejkaorp)a1$q63y0%*a^&fv=y$(bbe5+(b")
# SECURITY WARNING: don"t run with debug turned on in production!
DEBUG = env.bool("TEXTA_DEBUG", default=True)
# ALLOWED HOSTS
ALLOWED_HOSTS = env.list("TEXTA_ALLOWED_HOSTS", default=["*"])

DATA_UPLOAD_MAX_MEMORY_SIZE = env.int("TEXTA_MAX_UPLOAD", default=1024 * 1024 * 1024)

NAN_LANGUAGE_TOKEN_KEY = "UNK"

# Directory of a placeholder plot image
EMPTY_PLOT_DIR = os.path.join(BASE_DIR, "toolkit", "tools", "default_plots", "no_plot.png")

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "corsheaders",
    "rest_framework",
    "rest_framework.authtoken",
    # Apps
    "toolkit.core",
    "toolkit.elastic",
    "toolkit.embedding",
    "toolkit.dataset_import",
    "toolkit.tagger",
    "toolkit.torchtagger",
    "toolkit.bert_tagger",
    "toolkit.mlp",
    "toolkit.topic_analyzer",
    "toolkit.regex_tagger",
    "toolkit.anonymizer",
    "toolkit.docparser",
    "toolkit.evaluator",
    "toolkit.summarizer",
    "toolkit.celery_management",
    "toolkit.rakun_keyword_extractor",
    "toolkit.crf_extractor",
    "toolkit.annotator",
    # TEXTA Extension Apps
    # "docscraper",
    # THIRD PARTY
    # https://github.com/goinnn/django-multiselectfield
    "multiselectfield",
    "django_filters",
    "dj_rest_auth",
    "dj_rest_auth.registration",
    "allauth",  # Comes with dj-rest-auth[with_social].
    "allauth.account",
    "allauth.socialaccount",
    "django_extensions",
    "drf_yasg",
]

# For registration (see: https://django-rest-auth.readthedocs.io/en/latest/installation.html#registration-optional)
SITE_ID = 1
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
# email verification is false because we don"t have server configured
ACCOUNT_EMAIL_VERIFICATION = "none"

# For corsheaders/external frontend
CSRF_HEADER_NAME = "HTTP_X_XSRF_TOKEN"
CSRF_COOKIE_NAME = "XSRF-TOKEN"
# For accessing a live backend server locally.
CORS_ORIGIN_WHITELIST = env.list("TEXTA_CORS_ORIGIN_WHITELIST", default=["http://localhost:4200", 'https://law-test-8795b.web.app'])
CSRF_TRUSTED_ORIGINS = env.list("TEXTA_CSRF_TRUSTED_ORIGINS", default=["localhost"])
CORS_ALLOW_HEADERS = list(default_headers) + ["x-xsrf-token"]
CORS_ALLOW_CREDENTIALS = env.bool("TEXTA_CORS_ALLOW_CREDENTIALS", default=True)
CORS_ALLOW_ALL_ORIGINS = env.bool("TEXTA_CORS_ALLOW_ALL_ORIGINS", default=False)

# CF UAA OAUTH OPTIONS
USE_UAA = env.bool("TEXTA_USE_UAA", default=False)
UAA_SCOPES = env.str("TEXTA_UAA_SCOPES", default="openid texta.*")

UAA_SUPERUSER_SCOPE = env.str("TEXTA_UAA_SUPERUSER_SCOPE", default="texta.admin")
UAA_PROJECT_ADMIN_SCOPE = env.str("TEXTA_UAA_PROJECT_ADMIN_SCOPE", default="texta.project_admin")
UAA_TEXTA_SCOPE_PREFIX = env.str("TEXTA_UAA_SCOPE_PREFIX", default="texta")

# UAA server URL
UAA_URL = env("TEXTA_UAA_URL", default="http://localhost:8080/uaa")

UAA_OAUTH_TOKEN_URI = env("TEXTA_UAA_OAUTH_URI", default=f"{UAA_URL}/oauth/token")
UAA_USERINFO_URI = env("TEXTA_UAA_USERINFO_URI", default=f"{UAA_URL}/userinfo")
UAA_LOGOUT_URI = env("TEXTA_UAA_LOGOUT_URI", default=f"{UAA_URL}/logout.do")
UAA_AUTHORIZE_URI = env("TEXTA_UAA_AUTHORIZE_URI", default=f"{UAA_URL}/oauth/authorize")

# Callback URL defined on the UAA server, to which the user will be redirected after logging in on UAA
UAA_REDIRECT_URI = env("TEXTA_UAA_REDIRECT_URI", default="http://localhost:8000/api/v2/uaa/callback")
# TEXTA front URL where the user will be redirected after the redirect_uri
# Default value is for when running the front-end separately.
UAA_FRONT_REDIRECT_URL = env("TEXTA_UAA_FRONT_REDIRECT_URL", default="http://localhost:4200/oauth/uaa")
# OAuth client application (eg texta_toolkit) id and secret.
UAA_CLIENT_ID = env("TEXTA_UAA_CLIENT_ID", default="login")
UAA_CLIENT_SECRET = env("TEXTA_UAA_CLIENT_SECRET", default="loginsecret")
# For reference:
# https://docs.cloudfoundry.org/concepts/architecture/uaa.html
# https://docs.cloudfoundry.org/api/uaa/version/74.24.0/index.html
# https://www.oauth.com/


REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.NamespaceVersioning",
    "DEFAULT_VERSION": "v2",
    "ALLOWED_VERSIONS": ["v1", "v2"],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        # For DRF API browser pages
        "rest_framework.authentication.SessionAuthentication",
        # For authenticating requests with the Token
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_METADATA_CLASS": "toolkit.metadata.CustomMetadata",
    "DEFAULT_PAGINATION_CLASS": "toolkit.pagination.PageNumberPaginationDataOnly",
    "PAGE_SIZE": 30,
}

# Optionally include UaaAuthentication for CloudFoundry UAA OAuth 2.0 authentication
if USE_UAA:
    REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES'].insert(0, "toolkit.uaa_auth.authentication.UaaAuthentication")

REST_AUTH_SERIALIZERS = {
    "USER_DETAILS_SERIALIZER": "toolkit.core.user_profile.serializers.UserSerializer",
}

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# we can optionally disable csrf for testing purposes
USE_CSRF = env.bool("TEXTA_USE_CSRF", default=False)
if USE_CSRF:
    MIDDLEWARE.append("django.middleware.csrf.CsrfViewMiddleware")
else:
    # Add additional middleware to turn off the CSRF handling in the SessionsMiddleware.
    MIDDLEWARE.append("toolkit.tools.common_utils.DisableCSRFMiddleware")

ROOT_URLCONF = "toolkit.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "toolkit.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": env("DJANGO_DATABASE_ENGINE", default="django.db.backends.sqlite3"),
        "NAME": env("DJANGO_DATABASE_NAME", default=os.path.join(BASE_DIR, "data", "db.sqlite3")),
        "USER": env("DJANGO_DATABASE_USER", default=""),  # Not used with sqlite3.
        "PASSWORD": env("DJANGO_DATABASE_PASSWORD", default=""),  # Not used with sqlite3.
        "HOST": env("DJANGO_DATABASE_HOST", default=""),
        # Set to empty string for localhost. Not used with sqlite3.
        "PORT": env("DJANGO_DATABASE_PORT", default=""),
        # Set to empty string for default. Not used with sqlite3.
        "BACKUP_COUNT": 5,
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
LANGUAGE_CODE = "en"
TIME_ZONE = "Europe/Tallinn"
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.1/howto/static-files/

STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "static")

ELASTIC_CLUSTER_VERSION = env.int("TEXTA_ELASTIC_VERSION", default=7)

# Some existing descriptions are the size of a model, this should be a higher
# number to allow for description that contain a fair number of meta information in it.
# Changing these values will require a new migration to be created and applied.
DESCRIPTION_CHAR_LIMIT = 1000
ES_TIMEOUT_MAX = 100
ES_BULK_SIZE_MAX = 500

# OTHER ELASTICSEARCH OPTIONS
ES_CONNECTION_PARAMETERS = {
    "use_ssl": env.bool("TEXTA_ES_USE_SSL", default=False),
    "verify_certs": env.bool("TEXTA_ES_VERIFY_CERTS", default=False),
    "ca_certs": env("TEXTA_ES_CA_CERT_PATH", default=None),
    "client_cert": env("TEXTA_ES_CLIENT_CERT_PATH", default=None),
    "client_key": env("TEXTA_ES_CLIENT_KEY_PATH", default=None),
    "timeout": env.int("TEXTA_ES_TIMEOUT", default=60),
    "sniff_on_start": env.bool("TEXTA_ES_SNIFF_ON_START", default=True),
    "sniff_on_connection_fail": env.bool("TEXTA_ES_SNIFF_ON_FAIL", default=True)
}

### CELERY ###

# Amount of documents processed in a single task.
# Consider that processed text might be the size of a simple comment
# or a whole article.
MLP_BATCH_SIZE = env.int("TEXTA_MLP_BATCH_SIZE", default=25)
MLP_DEFAULT_LANGUAGE = env.str("TEXTA_MLP_DEFAULT_LANGUAGE", default="en")

# By default, the DB with number 0 is used in Redis. Other applications or instances of TTK should avoid using the same DB number.
BROKER_URL = env('TEXTA_REDIS_URL', default='redis://localhost:6379')
CELERY_RESULT_BACKEND = BROKER_URL
CELERY_ACCEPT_CONTENT = ["application/json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERYD_PREFETCH_MULTIPLIER = env.int("TEXTA_CELERY_PREFETCH_MULTIPLIER", default=1)
CELERY_ALWAYS_EAGER = env.bool("TEXTA_CELERY_ALWAYS_EAGER", default=False)

CELERY_USED_QUEUES = env.list("TEXTA_CELERY_USED_QUEUES", default=[CELERY_LONG_TERM_TASK_QUEUE, CELERY_SHORT_TERM_TASK_QUEUE, CELERY_MLP_TASK_QUEUE])

# Although Celery by default creates queues it's fed automatically, defining the queues manually in here is important
# for Celery operations like the purging of tasks. Lacking these, certain commands will default to the queue of CELERY_DEFAULT_QUEUE.
# TODO Figure out a way to instruct the deploying user on whether a non-registered queue exists in Redis, informing them to it to the env variable.
CELERY_QUEUES = (
    Queue(queue, exchange=queue, routing_key=queue)
    for queue in CELERY_USED_QUEUES
)

# By default use the queue for short term tasks, unless specified to use the long term one.
CELERY_DEFAULT_QUEUE = CELERY_SHORT_TERM_TASK_QUEUE
CELERY_DEFAULT_EXCHANGE = CELERY_SHORT_TERM_TASK_QUEUE
CELERY_DEFAULT_ROUTING_KEY = CELERY_SHORT_TERM_TASK_QUEUE

CELERYBEAT_SCHEDULE = {
    'sync_indices_in_elasticsearch': {
        'task': 'sync_indices_in_elasticsearch',
        'schedule': timedelta(minutes=env.int("TEXTA_INDEX_SYNC_INTERVAL_IN_MINUTES", default=1)),
        'options': {"queue": CELERY_DEFAULT_QUEUE}
    }
}

### DATA DIRECTORIES

# data dir for files generated by TK
DATA_DIR = env("TEXTA_DATA_DIR", default=os.path.join(BASE_DIR, "data"))
# base dir for 3rd party models (e.g. MLP or BERT)
# defaults to "external" in data dir
EXTERNAL_DATA_DIR = env("TEXTA_EXTERNAL_DATA_DIR", default=os.path.join(DATA_DIR, "external"))
# cache folder for BERT
CACHE_DIR_DEFAULT = os.path.join(EXTERNAL_DATA_DIR, ".cache")
CACHE_DIR = env("TEXTA_CACHE_DIR", default=CACHE_DIR_DEFAULT)
BERT_CACHE_DIR = os.path.join(CACHE_DIR, "bert")

# For whatever mythical reason, the transformer library does not respect the cache_dir parameter,
# hence we set it through an env variable in a roundabout way...
os.environ["TRANSFORMERS_CACHE"] = BERT_CACHE_DIR

# tk trained models dir
MODELS_DIR_DEFAULT = os.path.join(DATA_DIR, "models")
RELATIVE_MODELS_PATH = env("TEXTA_RELATIVE_MODELS_DIR", default=MODELS_DIR_DEFAULT)
# Facebook Model Suffix
FACEBOOK_MODEL_SUFFIX = env("FACEBOOK_MODEL_SUFFIX", default="facebook")
# MLP model dir
MLP_MODEL_DIRECTORY = env("TEXTA_MLP_MODEL_DIRECTORY_PATH", default=os.path.join(EXTERNAL_DATA_DIR, "mlp"))
# BERT pretrained models
BERT_PRETRAINED_MODEL_DIRECTORY = os.path.join(EXTERNAL_DATA_DIR, "bert_tagger", "pretrained")
# BERT fine-tuned models
BERT_FINETUNED_MODEL_DIRECTORY = os.path.join(RELATIVE_MODELS_PATH, "bert_tagger", "fine_tuned")
# NLTK data dir
NLTK_DATA_DIRECTORY = env("TEXTA_NLTK_DATA_DIRECTORY_PATH", default=os.path.join(EXTERNAL_DATA_DIR, "nltk"))

# create protected media dirs
MEDIA_DIR = os.path.join(DATA_DIR, "media")
MEDIA_URL = "data/media/"

LOG_PATH = os.path.join(DATA_DIR, "log")

UPLOAD_PATH = os.path.join(DATA_DIR, "upload")

# Path to the directory containing test files
TEST_DATA_DIR = os.path.join(DATA_DIR, "test")

# default BERT models
DEFAULT_BERT_MODELS = env.list("TEXTA_BERT_MODELS", default=["bert-base-multilingual-cased", "EMBEDDIA/finest-bert", "bert-base-uncased"])

# default MLP languages
DEFAULT_MLP_LANGUAGE_CODES = env.list("TEXTA_LANGUAGE_CODES", default=[])

# Enable GPU usage in MLP
MLP_USE_GPU = env.bool("TEXTA_MLP_USE_GPU", default=False)
# Select GPU device if more than one
MLP_GPU_DEVICE_ID = env.int("TEXTA_MLP_GPU_DEVICE_ID", default=0)

# default DS choices
DEFAULT_TEXTA_DATASOURCE_CHOICES = parse_tuple_env_headers("TEXTA_DATASOURCE_CHOICES", [
    ('emails', 'emails'),
    ('news articles', 'news articles'),
    ('comments', 'comments'),
    ('court decisions', 'court decisions'),
    ('tweets', 'tweets'),
    ('forum posts', 'forum posts'),
    ('formal documents', 'formal documents'),
    ('other', 'other')
])

# Logger IDs, used in apps.
INFO_LOGGER = "info_logger"
ERROR_LOGGER = "error_logger"
# Paths to info and error log files.
INFO_LOG_FILE_NAME = os.path.join(LOG_PATH, "info.log")
ERROR_LOG_FILE_NAME = os.path.join(LOG_PATH, "error.log")
LOGGING = setup_logging(INFO_LOG_FILE_NAME, ERROR_LOG_FILE_NAME, INFO_LOGGER, ERROR_LOGGER)

# Swagger Documentation
SWAGGER_SETTINGS = {
    "DEFAULT_AUTO_SCHEMA_CLASS": "toolkit.tools.swagger.CompoundTagsSchema"
}

ALLOW_BERT_MODEL_DOWNLOADS = env.bool("TEXTA_ALLOW_BERT_MODEL_DOWNLOADS", default=True)

RELATIVE_PROJECT_DATA_PATH = env("TOOLKIT_PROJECT_DATA_PATH", default=os.path.join(DATA_DIR, "projects"))

# Different types of models
MODEL_TYPES = ["embedding", "tagger", "torchtagger", "bert_tagger", "crf"]

# Ensure all the folders exists before downloading the resources.
prepare_mandatory_directories(
    EXTERNAL_DATA_DIR,
    BERT_PRETRAINED_MODEL_DIRECTORY,
    BERT_FINETUNED_MODEL_DIRECTORY,
    NLTK_DATA_DIRECTORY,
    MEDIA_DIR,
    LOG_PATH,
    UPLOAD_PATH,
    TEST_DATA_DIR,
    RELATIVE_PROJECT_DATA_PATH,
    *[os.path.join(RELATIVE_MODELS_PATH, model_type) for model_type in MODEL_TYPES]
)

### RESOURCE DOWNLOADS
SKIP_MLP_RESOURCES = env.bool("SKIP_MLP_RESOURCES", default=False)
if SKIP_MLP_RESOURCES is False:
    download_mlp_requirements(MLP_MODEL_DIRECTORY, DEFAULT_MLP_LANGUAGE_CODES, logging.getLogger(INFO_LOGGER))

SKIP_BERT_RESOURCES = env.bool("SKIP_BERT_RESOURCES", default=False)
if SKIP_BERT_RESOURCES is False:
    # Download pretrained models with weights initiated for binary classification (using state dict with initialized weights is disabled for multiclass)
    download_bert_requirements(BERT_PRETRAINED_MODEL_DIRECTORY, DEFAULT_BERT_MODELS, BERT_CACHE_DIR, logging.getLogger(INFO_LOGGER), num_labels=2)

SKIP_NLTK_RESOURCES = env.bool("SKIP_NLTK_RESOURCES", default=False)
if SKIP_NLTK_RESOURCES is False:
    download_nltk_resources(NLTK_DATA_DIRECTORY)
