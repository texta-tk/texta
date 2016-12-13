.. _configuration:


Configuration
======================

TEXTA's configuration is in :download:`settings.py <../../../settings.py>` file, which contains both adjustable and unadjustable options.
Adjustable options allow to tailor the paths, addresses and backend to one's needs, while altering unadjustable options will break the
application. Unadjustable options are mostly related to Django.

For most part, TEXTA has dual settings. This means that one can switch between development and production configuration, 
while having to change just a single variable *SERVER_TYPE*.

SERVER_TYPE determines several paths and addresses, which should be changed if not running on local host.

.. code-block:: python

    URL_PREFIX_DOMAIN = 'http://localhost:8000'
    URL_PREFIX_RESOURCE = ''
    ROOT_URLCONF = 'texta.urls'
    STATIC_URL = URL_PREFIX_DOMAIN + '/static/'
    STATIC_ROOT = os.path.join(BASE_DIR, 'static')
    DEBUG = True

The most important variables are *URL_PREFIX_\**. *URL_PREFIX_DOMAIN* specifies the address of the server hosting TEXTA and
*URL_PREFIX_RESOURCE* yields the resource path of TEXTA, if many applications are registered for a single domain.

*ROOT_URLCONF* is for Django's inner workings and should not be changed unless package structure is altered. *STATIC\** should be changed
only when running development version locally and for some reason static paths are aletered.

*DEBUG* determines whether stacktrace and variable values are shown when error occurs while server is generating a response.

.. code-block:: python

    ALLOWED_HOSTS = ['localhost','texta.stacc.ee','textadev.stacc.ee']
    
*ALLOWED_HOSTS* lists all allowed host headers to which the server responds. Prevents host poisoning. Should change when running TEXTA remotely.


User data
---------

By default TEXTA uses `SQLITE <https://sqlite.org/>`_ to store user created content. This can be changed by altering the *DATABASES* dictionary.

.. code-block:: python

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.path.join(BASE_DIR,'lex.db'),
            'USER': '',
            'PASSWORD': '',
            'HOST': '',
            'PORT': '',
        }
    }
    
Other possible engines include *postgresql_psycopg2*, *postgresql*, *mysql* and *oracle*.

If **privacy** is an issue, then a new *SECRET_KEY* should be generated and kept private. *SECRET_KEY* is used in Django as a seed for several 
hashes.


Elasticsearch
-------------

TEXTA relies heavily on Elasticsearch to allow full-text indexing and other text related queries.

The most important is to specify Elasticsearch address. It can be either edited in the *settings.py*

.. code-block:: python

    es_url = 'http://localhost:9200'
    es_url = 'http://elasticsearch2.stacc.ee:9201'
    
or set in the environment variables as *TEXTA_ELASTICSEARCH_URL*.

To fully utilize TEXTA's text summarization power, the temporal data in Elasticsearch should follow a certain format.

By default TEXTA assumes

.. code-block:: python

    date_format = 'yyyy-MM-dd'
    
but it can be changed, if it's more convenient.

If Elastichsearch is protected by authentication

.. code-block:: python

    es_use_ldap = False
    
should be set to True and *TEXTA_LDAP_USER* and *TEXTA_LDAP_PASSWORD* environment variables should have appropriate values.

Another possibility is to edit

.. code-block:: python

    es_ldap_user = os.getenv('TEXTA_LDAP_USER')
    es_ldap_password = os.getenv('TEXTA_LDAP_PASSWORD')
    

Logging
-------

TEXTA logs info and errors separately. Info includes requests, calculation results etc. Logging behaviour can be changed by altering

.. code-block:: python

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

By default TEXTA uses simple *FileHandler* to store entire logs. If space is of issue, *RotatingFileHandler* should be considered.