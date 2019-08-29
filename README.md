Works with Python 3.6

Creating environment:

`conda env create -f environment.yaml`

Running migrations:

`python migrate.py`

Running application:

`python manage.py runserver`

`celery -A toolkit.taskman worker -l info`



Building Docker:

`docker build -t texta-rest -f docker/cpu.Dockerfile .`

Building Docker with GPU support:

`docker build -t texta-rest -f docker/gpu.Dockerfile .`
