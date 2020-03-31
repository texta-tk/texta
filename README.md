# TEXTA Toolkit 2

## Documentation

https://docs.texta.ee

## Wiki

https://git.texta.ee/texta/texta-rest/wikis/home

## Notes

Works with Python 3.6

Creating environment:

`conda env create -f environment.yaml`

Running migrations:

`python migrate.py`

Running application:

`python manage.py runserver`

`celery -A toolkit.taskman worker -l info`

Import testing data:

`python import_test_data.py`

Run all tests:

`python manage.py test`

Run tests for specific app:

`python manage.py test appname (eg python manage.py test toolkit.neurotagger)`

Run performance tests (not run by default as they are slow):

`python manage.py test toolkit.performance_tests`

Building Docker:

`docker build -t texta-rest:latest -f docker/Dockerfile .`

Running Docker:

`docker run -p 8000:8000 texta-rest:latest`

Building Docker with GPU support:

`docker build -t texta-rest:gpu-latest -f docker/gpu.Dockerfile .`

Running Docker with GPU support:

`docker run --gpus all -p 8000:8000 texta-rest:gpu-latest`


# Environment variables

## Deploy & Testing variables
* TEXTA_ADMIN_PASSWORD - Password of the admin user created on first run.
* TEXTA_USE_CSRF - Disable CSRF for integration tests.

## External services
* TEXTA_ES_URL - URL of the Elasticsearch instance including the protocol, host and port (ex. http://localhost:9200).
* TEXTA_MLP_URL - URL of the Texta MLP instance including the protocol, host and port (ex. http://localhost:5000).
* TEXTA_REDIS_URL - URL of the Redis instance including the protocol, host and port (ex. redis://localhost:6379).

## Django specifics
* TEXTA_ES_PREFIX - String used to limit Elasticsearch index access. Only indices matched will be the ones matching "{TEXTA_ES_PREFIX}*".
* TEXTA_CORS_ORIGIN_WHITELIST - Comma separated string of urls (**NO WHITESPACE**) for the CORS whitelist. Needs to include the protocol (ex. http://* or http://*,http://localhost:4200).
* TEXTA_ALLOWED_HOSTS - Comma separated string (**NO WHITESPACE**) representing the host/domain names that this Django site can serve (ex. * or *,http://localhost:4200).
* TEXTA_DEBUG - True/False values on whether to run Django in it's Debug mode or not.
* TEXTA_SECRET_KEY - String key for cryptographic security purposes. ALWAYS SET IN PRODUCTION.

## Database credentials
* DJANGO_DATABASE_ENGINE - https://docs.djangoproject.com/en/3.0/ref/settings/#engine
* DJANGO_DATABASE_NAME - The name of the database to use. For SQLite, it’s the full path to the database file. When specifying the path, always use forward slashes, even on Windows.
* DJANGO_DATABASE_USER - The username to use when connecting to the database. Not used with SQLite.
* DJANGO_DATABASE_PASSWORD - The password to use when connecting to the database. Not used with SQLite.
* DJANGO_DATABASE_HOST - Which host to use when connecting to the database. An empty string means localhost. Not used with SQLite.
* DJANGO_DATABASE_PORT - The port to use when connecting to the database. An empty string means the default port. Not used with SQLite.

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