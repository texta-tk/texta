import os
import warnings

from corsheaders.defaults import default_headers
from kombu import Exchange, Queue

from .helper_functions import parse_list_env_headers
from .logging_settings import setup_logging


### CORE SETTINGS ###
# NOTE: THESE ARE INITIAL VARIABLES IMPORTED FROM THE ENVIRONMENT
# DO NOT IMPORT THESE VARIABLES IN APPS, BECAUSE THEY CAN BE OVERWRITTEN WITH VALUES FROM DB
# INSTEAD USE get_setting_val() function, e.g.:
# from toolkit.core.settings import get_core_setting
# ES_URL = get_core_setting("ES_URL")
CORE_SETTINGS = {
    "TEXTA_ES_URL": os.getenv("TEXTA_ES_URL", "http://localhost:9200"),
    "TEXTA_ES_PREFIX": os.getenv("TEXTA_ES_PREFIX", ""),
    "TEXTA_ES_USERNAME": os.getenv("TEXTA_ES_USER", ""),
    "TEXTA_ES_PASSWORD": os.getenv("TEXTA_ES_PASSWORD", ""),
    "TEXTA_MLP_URL": os.getenv("TEXTA_MLP_URL", "http://mlp-dev.texta.ee:5000")
}
### END OF CORE SETTINGS ###


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
    "drf_yasg"
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
    "DEFAULT_AUTHENTICATION_CLASSES": (
        # For DRF API browser pages
        "rest_framework.authentication.SessionAuthentication",
        # For authenticating requests with the Token
        "rest_framework.authentication.TokenAuthentication",
    ),
    "DEFAULT_PAGINATION_CLASS": "toolkit.pagination.PageNumberPaginationDataOnly",
    "PAGE_SIZE": 30,
}

REST_AUTH_SERIALIZERS = {
    "USER_DETAILS_SERIALIZER": "toolkit.core.user_profile.serializers.UserSerializer",
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
# we can optionally disable csrf for testing purposes
USE_CSRF = False if os.getenv("TEXTA_USE_CSRF", "False") == "False" else True
if USE_CSRF:
    MIDDLEWARE.append("django.middleware.csrf.CsrfViewMiddleware")
else:
    # Add additional middleware to turn off the CSRF handling in the SessionsMiddleware.
    MIDDLEWARE.append("toolkit.tools.common_utils.DisableCSRFMiddleware")

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

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

STATIC_URL = "api/v1/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "static")

# OTHER ELASTICSEARCH OPTIONS
ES_CONNECTION_PARAMETERS = {
    "use_ssl": True if os.getenv("TEXTA_ES_USE_SSL", None) == "True" else None,
    "verify_certs": True if os.getenv("TEXTA_ES_VERIFY_CERTS", None) == "True" else None,
    "ca_certs": os.getenv("TEXTA_ES_CA_CERT_PATH", None),
    "client_cert": os.getenv("TEXTA_ES_CLIENT_CERT_PATH", None),
    "client_key": os.getenv("TEXTA_ES_CLIENT_KEY_PATH", None),
    "timeout": int(os.getenv("TEXTA_ES_TIMEOUT")) if os.getenv("TEXTA_ES_TIMEOUT", None) else 10,
    "sniff_on_start": True if os.getenv("TEXTA_ES_SNIFF_ON_START", "True") == "True" else False,
    "sniff_on_connection_fail": True if os.getenv("TEXTA_ES_SNIFF_ON_FAIL", "True") == "True" else False
}

# CELERY OPTIONS
BROKER_URL = os.getenv("TEXTA_REDIS_URL", "redis://localhost:6379")
CELERY_RESULT_BACKEND = BROKER_URL
CELERY_ACCEPT_CONTENT = ["application/json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERYD_PREFETCH_MULTIPLIER = 1
CELERY_ALWAYS_EAGER = False if os.getenv("TEXTA_CELERY_ALWAYS_EAGER", "False") == "False" else True

CELERY_QUEUES = (
    Queue('long_term_tasks', exchange="long_term_tasks", routing_key='long_term_tasks'),
    Queue('short_term_tasks', exchange="short_term_tasks", routing_key='short_term_tasks'),
)

# By default use the queue for short term tasks, unless specified to use the long term one.
CELERY_DEFAULT_QUEUE = 'short_term_tasks'
CELERY_DEFAULT_EXCHANGE = 'short_term_tasks'
CELERY_DEFAULT_ROUTING_KEY = 'short_term_tasks'

# we set num workers to 1 because celery tasks are not allowed to have deamon processes
NUM_WORKERS = 1

DATA_FOLDER_NAME = os.getenv("TEXTA_DATA_FOLDER_NAME", "data")
MODELS_FOLDER_NAME = os.getenv("TEXTA_MODELS_FOLDER_NAME", "models")

MODELS_DIR_DEFAULT = os.path.join(BASE_DIR, DATA_FOLDER_NAME, MODELS_FOLDER_NAME)
MODELS_DIR = os.getenv("TEXTA_MODELS_DIR", os.path.join(BASE_DIR, DATA_FOLDER_NAME, MODELS_FOLDER_NAME))

MODEL_TYPES = ["embedding", "tagger", "torchtagger"]
for model_type in MODEL_TYPES:
    model_dir = os.path.join(MODELS_DIR, model_type)
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
