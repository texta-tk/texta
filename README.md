# TEXTA Toolkit 3

## Documentation

https://docs.texta.ee

## Wiki

https://git.texta.ee/texta/texta-rest/wikis/home

## Notes

Works with Python 3.8

### Creating environment:

`conda env create -f environment.yaml`

Running migrations:

`python3 migrate.py`

* This script will also create an admin account with the default username "admin". You can
  use ```python migrate.py -u {{username}}``` instead for a custom username of your choice.
* Password for that admin account will be generated automatically and printed to the console. This behaviour can be
  overwritten with the environment variable `TEXTA_ADMIN_PASSWORD`, in which case the password will be set to the same
  value as 'TEXTA_ADMIN_PASSWORD'.
* Running ```python migrate.py -o``` will overwrite the password with whatever value you have inside the environment
  variable `TEXTA_ADMIN_PASSWORD`.

Running application:

`python3 manage.py runserver`

`celery -A toolkit.taskman worker -l info`

Import testing data:

`python3 import_test_data.py`

Run all tests:

`python3 manage.py test`

Run tests for specific app:

`python3 manage.py test appname (eg python3 manage.py test toolkit.neurotagger)`

Run performance tests (not run by default as they are slow):

`python3 manage.py test toolkit.performance_tests`

Building Docker:

`docker build -t texta-rest:latest -f docker/Dockerfile .`

Running Docker:

`docker run -p 8000:8000 texta-rest:latest`

Building Docker with GPU support:

`docker build -t texta-rest:gpu-latest -f docker/gpu.Dockerfile .`

Running Docker with GPU support requires NVIDIA Container Toolkit to be installed on the host
machine: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html#docker. When Container
Toolkit is installed:

`docker run --gpus all -p 8000:8000 texta-rest:latest-gpu`

# Environment variables

## Deploy & Testing variables

* TEXTA_ENV_FILE - Optional file path for a typical .env file to be loaded into memory for TEXTA Toolkit (Default: None).
* TEXTA_SECRET_KEY - ***String key for cryptographic security purposes. ALWAYS SET IN PRODUCTION.***

* TEXTA_CORS_ALLOW_CREDENTIALS - Whether to allow cookies to be included in cross-site HTTP requests (Default: True)
* TEXTA_CORS_ALLOW_ALL_ORIGINS - Whether to allow requests from all Origins (Default: false)

* TEXTA_CELERY_USED_QUEUES - Comma separated list of Celery queues you are using for TEXTA Toolkit. No need to touch when running a standard configuration.
* TEXTA_ELASTIC_VERSION - Must equal to the integer of the main Elasticsearch cluster version (Default: 6).
* TEXTA_DEPLOY_KEY - Used to separate different Toolkit instances for cases where Elasticsearch or the database are
  shared amongst multiple instances. Best to give this a simple number (Default: 1).
* TEXTA_ADMIN_PASSWORD - Password of the admin user created on first run.
* TEXTA_USE_CSRF - Whether to disable CSRF for integration tests (Default: false).
* TEXTA_CELERY_ALWAYS_EAGER - Whether to use Celerys async features or not, useful for testing purposes locally. (
  Default: False)


* TEXTA_DATA_DIR - Path to the directory in which TEXTA Toolkit saves the models it generates, and the binary model
  dependencies it needs (Default: data).
* TEXTA_EXTERNAL_DATA_DIR - Path to the base directory in which 3rd party models (MLP/BERT/etc) are kept (Default:
  data/models).
* TEXTA_CACHE_DIR - Path for the cache folder which BERT uses (Default: data/external/.cache).
* TEXTA_RELATIVE_MODELS_DIR - Relative path of the directory in which all the different types of models are stored in.
  (Default: "/data/models").
* TEXTA_LANGUAGE_CODES - Comma separated string of Stanza supported language codes to use for Multilingual Processing.
  (Default: "").
* TEXTA_MLP_USE_GPU - Use GPU to speed up MLP (Default: False).
* TEXTA_MLP_MODEL_DIRECTORY_PATH - Relative path to the directory into which Stanza models will be stored under the "
  stanza" folder (setting this to ./home/texta will create ./home/texta/stanza which contains subfolders for every
  language like ./home/texta/stanza/et etc). (Default: "./data/external/mlp").
* TEXTA_MLP_DEFAULT_LANGUAGE - Language code of the language the MLP module will default to when trying to analyze a document whichs language it could not detect properly (Default: en).
* TEXTA_ALLOW_BERT_MODEL_DOWNLOADS - Boolean flag indicating if the users can download additional BERT models.
  (Default: True).
* TEXTA_BERT_MODEL_DIRECTORY_PATH - Relative path to the directory into which pretrained and fine-tuned BERT models will
  be stored under the "bert_tagger" folder. (setting this to ./home/texta will create
  ./home/texta/bert_tagger/pretrained/ which contains subfolders for every downloaded bert more like
  ./home/texta/bert_model/pretrained/bert-base-multilingual-cased etc and ./home/texta/bert_model/fine_tuned/ which will
  store fine-tuned BERT models. (Default: "./data/models").
* TEXTA_NLTK_DATA_DIRECTORY_PATH - Path of the directory where the NLTK library keeps its resources (Default:
  data/external/nltk).
* TEXTA_BERT_MODELS - Comma seprated string of pretrained BERT models to download.
  (Default: "bert-base-multilingual-cased,bert-base-uncased,EMBEDDIA/finest-bert").
* SKIP_BERT_RESOURCES - If set "True", skips downloading pretrained BERT models. (Default: false).
* SKIP_MLP_RESOURCES - Whether to skip downloading MLP resources on application boot-up (Default: false).
* SKIP_NLTK_RESOURCES - Whether to skip downloading NLTK library resources on application boot-up (Default: false).
* TEXTA_EVALUATOR_MEMORY_BUFFER_GB - The minimum amount of memory that should be left free while using the evaluator,
  unit = GB. (Default = 50% of available_memory)
* TEXTA_DATASOURCE_CHOICES - Choices for index domain field given as a list ex: [['prefix_name', 'display_name']]. (
  Default = [["emails", "emails"], ["news articles", "news articles"], ["comments", "comments"]
  , ["court decisions", "court decisions"], ["tweets", "tweets"], ["forum posts", "forum posts"]
  , ["formal documents", "formal documents"], ["other", "other"]])

* TOOLKIT_PROJECT_DATA_PATH - Path of the directory in which project specific data is kept (Default: data/projects).

## External services
* TEXTA_ES_PREFIX - String used to limit Elasticsearch index access. Only indices matched will be the ones matching "
  {TEXTA_ES_PREFIX}*".
* TEXTA_ES_URL - URL of the Elasticsearch instance including the protocol, host and port (ex. http://localhost:9200).
* TEXTA_REDIS_URL - URL of the Redis instance including the protocol, host and port (ex. redis://localhost:6379).

## Django specifics

* TEXTA_CORS_ORIGIN_WHITELIST - Comma separated string of urls (**NO WHITESPACE**) for the CORS whitelist. Needs to
  include the protocol (ex. http://* or http://*,http://localhost:4200).
* TEXTA_ALLOWED_HOSTS - Comma separated string (**NO WHITESPACE**) representing the host/domain names that this Django
  site can serve (ex. * or *,http://localhost:4200).
* TEXTA_DEBUG - True/False values on whether to run Django in its Debug mode or not (Default: true).
* TEXTA_MAX_UPLOAD - Maximum size of files in bytes that are allowed to be updated, which Django validates (Default: 1073741824 aka 1GB)

## Database credentials

* DJANGO_DATABASE_ENGINE - https://docs.djangoproject.com/en/3.0/ref/settings/#engine
* DJANGO_DATABASE_NAME - The name of the database to use. For SQLite, it’s the full path to the database file. When
  specifying the path, always use forward slashes, even on Windows.
* DJANGO_DATABASE_USER - The username to use when connecting to the database. Not used with SQLite.
* DJANGO_DATABASE_PASSWORD - The password to use when connecting to the database. Not used with SQLite.
* DJANGO_DATABASE_HOST - Which host to use when connecting to the database. An empty string means localhost. Not used
  with SQLite.
* DJANGO_DATABASE_PORT - The port to use when connecting to the database. An empty string means the default port. Not
  used with SQLite.

## Docker specific configurations:
* TEXTA_SHORT_TASK_WORKERS - Number of processes available for short term tasks (Default: 2).
* TEXTA_LONG_TASK_WORKERS - Number of processes available for long term tasks (Default: 4).
* TEXTA_MLP_TASK_WORKERS - Number of processes available for MLP based tasks (Default: 2).
* TEXTA_SHORT_MAX_TASKS - Number of tasks per worker for short term tasks (Default: 10).
* TEXTA_LONG_MAX_TASKS - Number of tasks per worker for long term tasks (Default: 10).
* TEXTA_MLP_MAX_TASKS - Number of tasks per worker for MLP based tasks (Default: 10).
* TEXTA_BEAT_LOG_LEVEL - Which log level should beat output within the Docker image (Default: WARNING).
* TEXTA_CELERY_LOG_LEVEL - Which log level should Celery workers output within the Docker image (Default: WARNING).



## Extra Elasticsearch connection configurations

Unless you have a specially configured Elasticsearch instance, you can ignore these options.

* TEXTA_ES_USER - Username to authenticate to a secured Elasticsearch instance.
* TEXTA_ES_PASSWORD - Password to authenticate to a secured Elasticsearch instance.

https://elasticsearch-py.readthedocs.io/en/6.3.1/connection.html#elasticsearch.Urllib3HttpConnection:

* TEXTA_ES_USE_SSL
* TEXTA_ES_VERIFY_CERTS
* TEXTA_ES_CA_CERT_PATH
* TEXTA_ES_CLIENT_CERT_PATH
* TEXTA_ES_CLIENT_KEY_PATH
* TEXTA_ES_TIMEOUT
* TEXTA_ES_SNIFF_ON_START
* TEXTA_ES_SNIFF_ON_FAIL

## UAA specific configurations

* TEXTA_USE_UAA - Whether to include UAA authentication with the default authentication (Default: false).
* TEXTA_UAA_SCOPES - Which scopes should be sent with communication between TEXTA Toolkit and UAA (Default: openid
  texta.*).
* TEXTA_UAA_SUPERUSER_SCOPE - Which scope to use for determining whether an UAA user is a superuser (Default:
  texta.admin).
* TEXTA_UAA_PROJECT_ADMIN_SCOPE - Which scope to use to specify whether an UAA user has project administrator rights to
  ANY project which is available to them (Default: texta.project_admin).
* TEXTA_UAA_SCOPE_PREFIX - Prefix for determining UAA user access to TEXTA Toolkit. Any user who does not have a scope
  which matches the pattern "{TEXTA_UAA_SCOPE_PREFIX}.*" will be denied entry to TEXTA Toolkit (Default: texta).

* TEXTA_UAA_URL - URI for the UAA service (Default: http://localhost:8080).
* TEXTA_UAA_REDIRECT_URI - URI into which the user will be redirected after a successful UAA login (
  Default: http://localhost:8000/api/v2/uaa/callback).
* TEXTA_UAA_FRONT_REDIRECT_URL - Configuration for the front end to determine where it will redirect the user after a
  successful login with UAA by Toolkit (Default: http://localhost:4200/oauth/uaa)
* TEXTA_UAA_CLIENT_ID - UAA client ID for authenticating the TEXTA Toolkit application for UAA. ***Must be kept
  secret***
* TEXTA_UAA_CLIENT_SECRET - Password for authenticating the TEXTA Toolkit application with UAA. ***Must be kept
  secret***
