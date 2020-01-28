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

`python ./scripts/import_test_data.py`

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
