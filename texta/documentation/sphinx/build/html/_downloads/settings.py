######################### TEXTA Configuration File ########################

# This file contains all the framework's general configurable options which
# don't need changes in the source code. Some configurations are hardcoded
# into different applications' source code and may be altered to fine-tune
# the output or calculation results. For all hardcoded configurations,
# consult #TODO.
# 
# Default configuration suffices for running a development version. For
# production, one needs to define server specific paths.
# 
# General options define file and URL paths, #TODO
# 
# Installation is covered in documentation at #TODO
# 

from time import strftime
import os

# Path to TEXTA's root directory. It is used in other paths as a prefix.
# BASE_DIR = os.path.realpath(os.path.dirname(__file__)) tries to determine
# the path programmatically but may occasionally fail.
# 
BASE_DIR = os.path.realpath(os.path.dirname(__file__))

############################ Server Type ###########################

# Server type allows to predetermine a wide range of options.
# It is used to switch between 'development' and 'production' instances,
# so that after setting up the variables, one only has to alter the
# SERVER_TYPE string to have a fully configured and functional instance. 
#
# The default development version is tuned for hosting TEXTA locally and
# needs no further configuration. However, if your development version is
# on a remote machine, consult 'production' settings.
# 
# URL_PREFIX_DOMAIN - domain address of the hosting server.
# URL_PREFIX_RESOURCE - resource which is responsible for hosting TEXTA
#                       application server.
# ROOT_URLCONF - Django's root urls.py file's package path.
# STATIC_URL - static directory's address.
# STATIC_ROOT - static directory's file path.
# DEBUG - whether to display verbose variable values and stack trace when
#         error occurs during page resolving.

SERVER_TYPE = 'development'

if SERVER_TYPE == 'development':
    URL_PREFIX_DOMAIN = 'http://localhost:8000'
    URL_PREFIX_RESOURCE = ''
    ROOT_URLCONF = 'texta.urls'
    STATIC_URL = URL_PREFIX_DOMAIN + '/static/'
    STATIC_ROOT = os.path.join(BASE_DIR, 'static')
    DEBUG = True
elif SERVER_TYPE == 'production':
    URL_PREFIX_DOMAIN = 'http://textadev.stacc.ee'
    URL_PREFIX_RESOURCE = '/texta'
    ROOT_URLCONF = 'texta.urls'
    STATIC_URL = '/texta/static/'
    DEBUG = False

########################### URLs and paths ###########################

# Defines URLs and paths which are used by various apps.

# URL to TEXTA's root. E.g. 'http://textadev.stacc.ee' or 'http://www.stacc.ee/texta'.
# Should not be altered.
#
URL_PREFIX = URL_PREFIX_DOMAIN + URL_PREFIX_RESOURCE

# URL to the application's login page. TEXTA's login page is its index page.
# Should not be altered. Needed for Django's auth module, used for redirecting
# when unauthorized user is attempting to access authorized content.
#
LOGIN_URL = URL_PREFIX

# Path to media files root directory.
# 
MEDIA_ROOT = os.path.join(BASE_DIR, 'files')

# URL to media files root.
# 
MEDIA_URL = '/files/'
ADMIN_MEDIA_PREFIX = '/media/'

# Path to users' visited words in Lex Miner.
# 
USER_MODELS = os.path.join(BASE_DIR,'data','usermodels')

# Path to users' language models.
# 
MODELS_DIR = os.path.join(BASE_DIR,'data','models')

if not os.path.exists(MODELS_DIR):
    os.makedirs(MODELS_DIR)

if not os.path.exists(MODELS_DIR):
    os.makedirs(MODELS_DIR)

STATICFILES_DIRS = (os.path.join(BASE_DIR, 'static_general'),) # TODO remove


ADMINS = (
    # ('Your Name', 'your_email@example.com'),
)

MANAGERS = ADMINS

# SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# List of all host headers which are accepted to prevent host header poisoning.
# Should be altered if hosted on a remote machine.
#
ALLOWED_HOSTS = ['localhost','texta.stacc.ee','textadev.stacc.ee']

# Defines which database backend does the application use. TEXTA uses only default with sqlite engine.
# Can change engine and database info as one sees fit.
#
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

# Key used for seed in various Django's features needing crypto or hashing.
#
SECRET_KEY = '+$18(*8p_h0u6-)z&zu^@=$2h@=8qe+3uwyv+3#v9*)fy9hy&f'

# Defines template engine and context processors to render dynamic HTML pages.
# 
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
                'texta.utils.context_processors.get_version'
            ],
            'loaders': [
                'django.template.loaders.filesystem.Loader',
                'django.template.loaders.app_directories.Loader',
            ],
            'debug': DEBUG,
        },
    },
]

# List of Django plugins used in TEXTA.
# 
MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
)

# List of built-in and custom apps in use.
# 
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
    'texta.mwe_miner',
    'texta.account',
    'texta.home',
    'texta.corpus_tool',
    'texta.model_manager',
    'texta.ontology_viewer',
    'texta.base',
    'texta.permission_admin',
    'texta.grammar_builder',
    'texta.document_miner',
)

############################ Elasticsearch ###########################

# Elasticsearch connection settings. Elasticsearch is used throughout
# TEXTA to store the analyzed documents.
# 


# Elasticsearch URL with protocol specification. Can be either localhost
# or remote address.
#
es_url = os.getenv('TEXTA_ELASTICSEARCH_URL')
if es_url is None:
    es_url = 'http://localhost:9200'
    #es_url = 'http://elasticsearch2.stacc.ee:9201'

# Elasticsearch links to outside world
# ('index_name','mapping_name','field_name'):('url_prefix','url_suffix')
es_links = {
    ('etsa_new', 'event_dgn', 'epiId'): ('https://p12.stacc.ee/common/epicrisis/?id=', ''),
    ('etsa_new', 'event_dgn', 'patId'): ('https://p12.stacc.ee/common/aegread/index.php/aegrida/get/?id=', '')
    }

# Date format used in Elasticsearch fields.
# 
date_format = 'yyyy-MM-dd'

# Set to True if Elasticsearch needs authentication. Tested with basic auth.
es_use_ldap = False
es_ldap_user = os.getenv('TEXTA_LDAP_USER')
es_ldap_password = os.getenv('TEXTA_LDAP_PASSWORD')

############################### Logging ##############################

# TEXTA stores errors and query info in two different log files.
#

# Path to the log directory. Default is /log
# 
LOG_PATH = os.path.join(BASE_DIR,'log')

# Separator used to join different logged features.
#
logging_separator = ' - '

# Paths to info and error log files.
# 
info_log_file_name = os.path.join(LOG_PATH, "info.log")
error_log_file_name = os.path.join(LOG_PATH, "error.log")

# Logger IDs, used in apps. Do not change.
#
INFO_LOGGER = 'info_logger'
ERROR_LOGGER = 'error_logger'

# Most of the following logging settings can be changed.
# Especially format, logging levels, logging class and filenames.
#
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

############################ Boot scripts ###########################

# Several scripts ran during the boot to set up files and directories.
# Scripts will only be run if settings is imported from 'texta' directory, e.g. as a result of manager.py

if os.path.split(os.getcwd())[1] == 'texta':

    from texta.utils.setup import write_navigation_file, ensure_dir_existence

    write_navigation_file(URL_PREFIX, STATIC_URL)
    ensure_dir_existence(LOG_PATH)
    ensure_dir_existence(MODELS_DIR)
    ensure_dir_existence(USER_MODELS)
