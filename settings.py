from time import strftime
import os

DEBUG = True

SERVER_TYPE = 'DEV'

BASE_DIR = os.path.realpath(os.path.dirname(__file__))

ADMINS = (
    # ('Your Name', 'your_email@example.com'),
)

MANAGERS = ADMINS

# SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

if SERVER_TYPE == 'DEV':
    URL_PREFIX_DOMAIN = 'http://localhost:8000'
    URL_PREFIX_RESOURCE = ''
    ROOT_URLCONF = 'texta.urls'
    STATIC_URL = URL_PREFIX_DOMAIN + '/static/'
    STATIC_ROOT = os.path.join(BASE_DIR, 'static')
else:
    URL_PREFIX_DOMAIN = 'http://yourdomain.com'
    URL_PREFIX_RESOURCE = '/texta'
    ROOT_URLCONF = 'texta.urls'
    STATIC_URL = '/texta/static/'

URL_PREFIX = URL_PREFIX_DOMAIN + URL_PREFIX_RESOURCE

LOGIN_URL = URL_PREFIX

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
    # Add 'postgresql_psycopg2', 'postgresql', 'mysql', 'sqlite3' or 'oracle'.
        'NAME': os.path.join(BASE_DIR,'lex.db'),  # Or path to database file if using sqlite3.
        'USER': '',  # Not used with sqlite3.
        'PASSWORD': '',  # Not used with sqlite3.
        'HOST': '',  # Set to empty string for localhost. Not used with sqlite3.
        'PORT': '',  # Set to empty string for default. Not used with sqlite3.
    }
}

TIME_ZONE = 'Europe/Tallinn'
LANGUAGE_CODE = 'et'

SITE_ID = 1
USE_I18N = True
USE_L10N = True

MEDIA_ROOT = os.path.join(BASE_DIR, 'files')
MEDIA_URL = '/files/'
ADMIN_MEDIA_PREFIX = '/media/'

USER_MODELS = os.path.join(BASE_DIR,'data','usermodels')
MODELS_DIR = os.path.join(BASE_DIR,'data','models')

if not os.path.exists(MODELS_DIR):
    os.makedirs(MODELS_DIR)

if not os.path.exists(MODELS_DIR):
    os.makedirs(MODELS_DIR)

STATICFILES_DIRS = (os.path.join(BASE_DIR, 'static_general'),)

SECRET_KEY = '+$18(*8p_h0u6-)z&zu^@=$2h@=8qe+3uwyv+3#v9*)fy9hy&f'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR,'templates')],
        'APP_DIRS': False,
        'OPTIONS': {
            'context_processors': [
                'django.contrib.auth.context_processors.auth',
                'django.template.context_processors.debug',
                'django.template.context_processors.i18n',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                'django.template.context_processors.tz',
                'django.template.context_processors.request',
                'django.contrib.messages.context_processors.messages',
            ],
            'loaders': [
                'django.template.loaders.filesystem.Loader',
                'django.template.loaders.app_directories.Loader',
            ],
            'debug': DEBUG,
        },
    },
]

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.admin',
    'django.contrib.staticfiles',
    'texta.lm',
    'texta.conceptualiser',
    'texta.ontologiser',
    'texta.mwe_miner',
    'texta.account',
    'texta.home',
    'texta.corpus_tool',
    'texta.model_manager',
    'texta.ontology_viewer',
    'texta.base',
    'texta.permission_admin',
    'texta.grammar_builder',
    'texta.document_miner'
)

# Elasticsearch parameters
date_format = 'yyyy-MM-dd'
es_url = os.getenv('TEXTA_ELASTICSEARCH_URL')
if es_url is None:
    es_url = 'http://localhost:9200'
#    es_url = 'http://elasticsearch2.stacc.ee:9201'

# Elasticsearch links to outside world
# ('index_name','mapping_name','field_name'):('url_prefix','url_suffix')
es_links = {
    ('etsa_new', 'event_dgn', 'epiId'): ('https://p12.stacc.ee/common/epicrisis/?id=', ''),
    ('etsa_new', 'event_dgn', 'patId'): ('https://p12.stacc.ee/common/aegread/index.php/aegrida/get/?id=', '')
    }

# Logging settings
LOG_PATH = os.path.join(BASE_DIR,'log')
if not os.path.exists(LOG_PATH):
    os.makedirs(LOG_PATH)

logging_separator = ' - '
info_log_file_name = os.path.join(LOG_PATH, "info.log")
error_log_file_name = os.path.join(LOG_PATH, "error.log")

INFO_LOGGER = 'info_logger'
ERROR_LOGGER = 'error_logger'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'detailed': {
            'format': logging_separator.join(
                    ['%(levelname)s', '%(module)s', '%(name)s', '%(process)d', '%(thread)d', '%(message)s',
                     '%(asctime)s'])
        },
        'normal': {
            'format': logging_separator.join(['%(levelname)s', '%(module)s', '%(message)s', '%(asctime)s'])
        },
        'detailed_error': {
            'format': '\n' + logging_separator.join(
                    ['%(levelname)s', '%(module)s', '%(name)s', '%(process)d', '%(thread)d', '%(message)s',
                     '%(asctime)s'])
        }
    },
    'handlers': {
        'info_file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'formatter': 'detailed',
            'filename': info_log_file_name,
            'encoding': 'utf8',
            'mode': 'a'
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'formatter': 'detailed_error',
            'filename': error_log_file_name,
            'encoding': 'utf8',
            'mode': 'a'
        },
    },
    'loggers': {
        INFO_LOGGER: {
            'level': 'DEBUG',
            'handlers': ['info_file']
        },
        ERROR_LOGGER: {
            'level': 'ERROR',
            'handlers': ['error_file']
        }
    }
}
