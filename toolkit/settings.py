import logging
import os
import pathlib
import warnings

from corsheaders.defaults import default_headers
from kombu import Exchange, Queue

from .helper_functions import download_mlp_requirements, parse_list_env_headers
from .logging_settings import setup_logging


DEPLOY_KEY = os.getenv("TEXTA_DEPLOY_KEY", 1)

### CORE SETTINGS ###
# NOTE: THESE ARE INITIAL VARIABLES IMPORTED FROM THE ENVIRONMENT
# DO NOT IMPORT THESE VARIABLES IN APPS, BECAUSE THEY CAN BE OVERWRITTEN WITH VALUES FROM DB
# INSTEAD USE get_setting_val() function, e.g.:
# from toolkit.helper_functions import get_core_setting
# ES_URL = get_core_setting("ES_URL")
CORE_SETTINGS = {
    "TEXTA_ES_URL": os.getenv("TEXTA_ES_URL", "http://elastic-dev.texta.ee:9200"),
    "TEXTA_ES_PREFIX": os.getenv("TEXTA_ES_PREFIX", ""),
    "TEXTA_ES_USERNAME": os.getenv("TEXTA_ES_USER", ""),
    "TEXTA_ES_PASSWORD": os.getenv("TEXTA_ES_PASSWORD", ""),
}
### END OF CORE SETTINGS ###

TEXTA_TAGS_KEY = "texta_facts"

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("TEXTA_SECRET_KEY", "eqr9sjz-&baah&c%ejkaorp)a1$q63y0%*a^&fv=y$(bbe5+(b")
# SECURITY WARNING: don"t run with debug turned on in production!
DEBUG = True if os.getenv("TEXTA_DEBUG", "True") == "True" else False
# ALLOWED HOSTS
ALLOWED_HOSTS = parse_list_env_headers("TEXTA_ALLOWED_HOSTS", ["*"])

DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("TEXTA_MAX_UPLOAD", 1024 * 1024 * 1024))

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
    "toolkit.mlp",
    "toolkit.topic_analyzer",
    "toolkit.regex_tagger",
    "toolkit.anonymizer",
    "toolkit.docparser",
    "toolkit.document_importer",
    # TEXTA Extension Apps
    # "docscraper",
    # THIRD PARTY
    # https://github.com/goinnn/django-multiselectfield
    "multiselectfield",
    "django_filters",
    # "rest_auth" https://github.com/Tivix/django-rest-auth
    "rest_auth",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "rest_auth.registration",
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
CORS_ORIGIN_WHITELIST = parse_list_env_headers("TEXTA_CORS_ORIGIN_WHITELIST", ["http://localhost:4200"])
CORS_ALLOW_HEADERS = list(default_headers) + ["x-xsrf-token"]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = False if os.getenv("TEXTA_CORS_ALLOW_ALL_ORIGINS", "false").lower() == "false" else True

# CF UAA OAUTH OPTIONS
USE_UAA = False if os.getenv("TEXTA_USE_UAA", "false").lower() == "false" else True
# UAA server URL
UAA_URL = os.getenv("TEXTA_UAA_URL", "http://localhost:8080/uaa")
# Callback URL defined on the UAA server, to which the user will be redirected after logging in on UAA
UAA_REDIRECT_URI = os.getenv("TEXTA_UAA_REDIRECT_URI", "http://localhost:8000/api/v1/uaa/callback")
# TEXTA front URL where the user will be redirected after the redirect_uri
UAA_FRONT_REDIRECT_URL = os.getenv("TEXTA_UAA_FRONT_REDIRECT_URL", "http://localhost:4200/oauth")
# OAuth client application (eg texta_toolkit) id and secret.
UAA_CLIENT_ID = os.getenv("TEXTA_UAA_CLIENT_ID", "login")
UAA_CLIENT_SECRET = os.getenv("TEXTA_UAA_CLIENT_SECRET", "loginsecret")
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
    "DEFAULT_VERSION": "v1",
    "ALLOWED_VERSIONS": ["v1"],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        # For DRF API browser pages
        "rest_framework.authentication.SessionAuthentication",
        # For authenticating requests with the Token
        "rest_framework.authentication.TokenAuthentication",
    ],
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
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# we can optionally disable csrf for testing purposes
USE_CSRF = False if os.getenv("TEXTA_USE_CSRF", "false").lower() == "false" else True
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
        "ENGINE": os.getenv("DJANGO_DATABASE_ENGINE", "django.db.backends.sqlite3"),
        "NAME": os.getenv("DJANGO_DATABASE_NAME", os.path.join(BASE_DIR, "data", "db.sqlite3")),
        "USER": os.getenv("DJANGO_DATABASE_USER", ""),  # Not used with sqlite3.
        "PASSWORD": os.getenv("DJANGO_DATABASE_PASSWORD", ""),  # Not used with sqlite3.
        "HOST": os.getenv("DJANGO_DATABASE_HOST", ""),
        # Set to empty string for localhost. Not used with sqlite3.
        "PORT": os.getenv("DJANGO_DATABASE_PORT", ""),
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

# OTHER ELASTICSEARCH OPTIONS
ES_CONNECTION_PARAMETERS = {
    "use_ssl": False if os.getenv("TEXTA_ES_USE_SSL", "false").lower() == "false" else True,
    "verify_certs": False if os.getenv("TEXTA_ES_VERIFY_CERTS", "false").lower() == "false" else True,
    "ca_certs": os.getenv("TEXTA_ES_CA_CERT_PATH", None),
    "client_cert": os.getenv("TEXTA_ES_CLIENT_CERT_PATH", None),
    "client_key": os.getenv("TEXTA_ES_CLIENT_KEY_PATH", None),
    "timeout": int(os.getenv("TEXTA_ES_TIMEOUT")) if os.getenv("TEXTA_ES_TIMEOUT", None) else 10,
    "sniff_on_start": True if os.getenv("TEXTA_ES_SNIFF_ON_START", "true").lower() == "true" else True,
    "sniff_on_connection_fail": True if os.getenv("TEXTA_ES_SNIFF_ON_FAIL", "true").lower() == "true" else False
}

# CELERY
BROKER_URL = os.getenv('TEXTA_REDIS_URL', 'redis://localhost:6379')
CELERY_RESULT_BACKEND = BROKER_URL
CELERY_ACCEPT_CONTENT = ["application/json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERYD_PREFETCH_MULTIPLIER = 1
CELERY_ALWAYS_EAGER = False if os.getenv("TEXTA_CELERY_ALWAYS_EAGER", "false").lower() == "false" else True
CELERY_LONG_TERM_TASK_QUEUE = "long_term_tasks"
CELERY_SHORT_TERM_TASK_QUEUE = "short_term_tasks"
CELERY_MLP_TASK_QUEUE = "mlp_queue"

CELERY_QUEUES = (
    Queue(CELERY_LONG_TERM_TASK_QUEUE, exchange=CELERY_LONG_TERM_TASK_QUEUE, routing_key=CELERY_LONG_TERM_TASK_QUEUE),
    Queue(CELERY_SHORT_TERM_TASK_QUEUE, exchange=CELERY_SHORT_TERM_TASK_QUEUE, routing_key=CELERY_SHORT_TERM_TASK_QUEUE),
    Queue(CELERY_MLP_TASK_QUEUE, exchange=CELERY_MLP_TASK_QUEUE, routing_key=CELERY_MLP_TASK_QUEUE),
)

# By default use the queue for short term tasks, unless specified to use the long term one.
CELERY_DEFAULT_QUEUE = 'short_term_tasks'
CELERY_DEFAULT_EXCHANGE = 'short_term_tasks'
CELERY_DEFAULT_ROUTING_KEY = 'short_term_tasks'

# we set num workers to 1 because celery tasks are not allowed to have deamon processes
NUM_WORKERS = 1

MODELS_DIR_DEFAULT = str(pathlib.Path("data") / "models")
RELATIVE_MODELS_PATH = os.getenv("TEXTA_RELATIVE_MODELS_DIR", MODELS_DIR_DEFAULT)

DEFAULT_MLP_LANGUAGE_CODES = parse_list_env_headers("TEXTA_LANGUAGE_CODES", ["et", "en", "ru"])
MLP_MODEL_DIRECTORY = os.getenv("TEXTA_MLP_MODEL_DIRECTORY_PATH", MODELS_DIR_DEFAULT)

MODEL_TYPES = ["embedding", "tagger", "torchtagger"]
for model_type in MODEL_TYPES:
    model_dir = os.path.join(RELATIVE_MODELS_PATH, model_type)
    if not os.path.exists(model_dir):
        os.makedirs(model_dir)

# create protected media dirs
MEDIA_DIR = os.path.join(BASE_DIR, "data", "media")
if not os.path.exists(MEDIA_DIR):
    os.makedirs(MEDIA_DIR)
MEDIA_URL = "data/media/"

# Path to the log directory. Default is /log
LOG_PATH = os.path.join(BASE_DIR, "data", "log")
if not os.path.exists(LOG_PATH):
    os.makedirs(LOG_PATH)

# Path to the upload directory. Default is /upload
UPLOAD_PATH = os.path.join(BASE_DIR, "data", "upload")
if not os.path.exists(UPLOAD_PATH):
    os.makedirs(UPLOAD_PATH)

# Path to the directory containing test files
TEST_DATA_DIR = os.path.join(BASE_DIR, "data", "test")
if not os.path.exists(TEST_DATA_DIR):
    os.makedirs(TEST_DATA_DIR)

# Logger IDs, used in apps.
INFO_LOGGER = "info_logger"
ERROR_LOGGER = "error_logger"
# Paths to info and error log files.
INFO_LOG_FILE_NAME = os.path.join(LOG_PATH, "info.log")
ERROR_LOG_FILE_NAME = os.path.join(LOG_PATH, "error.log")
LOGGING = setup_logging(INFO_LOG_FILE_NAME, ERROR_LOG_FILE_NAME, INFO_LOGGER, ERROR_LOGGER)

# Ignore Python Warning base class
warnings.simplefilter(action="ignore", category=Warning)

# Swagger Documentation
SWAGGER_SETTINGS = {
    "DEFAULT_AUTO_SCHEMA_CLASS": "toolkit.tools.swagger.CompoundTagsSchema"
}

SKIP_MLP_RESOURCES = False if os.getenv("SKIP_MLP_RESOURCES", "false").lower() == "false" else True
if SKIP_MLP_RESOURCES is False:
    download_mlp_requirements(MLP_MODEL_DIRECTORY, DEFAULT_MLP_LANGUAGE_CODES, logging.getLogger(INFO_LOGGER))

RELATIVE_PROJECT_DATA_PATH = os.getenv("TOOLKIT_PROJECT_DATA_PATH", "data/projects/")
pathlib.Path(RELATIVE_PROJECT_DATA_PATH).mkdir(parents=True, exist_ok=True)

SEARCHER_FOLDER_KEY = "searcher"
