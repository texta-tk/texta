# TODO Remove nano and other development requirements.
# TODO Find out why it was neccessary to go into inside the container, delete all .pyc, .pycache, migrations and db.sqlite3 files.

FROM python:3.5.5
ENV PYTHONUNBUFFERED 1

RUN apt-get update && apt-get upgrade -y && apt-get autoremove && apt-get autoclean
RUN apt-get install -y --no-install-recommends nano libpulse-dev swig authbind
RUN pip install requests numpy cython  scipy sklearn gensim django==2.0.2 pathlib dateutils sympy textract elasticsearch elasticsearch_dsl psycopg2-binary psycopg2

RUN touch /etc/authbind/byport/80
RUN chmod 777 /etc/authbind/byport/80

RUN mkdir texta
COPY . texta/

WORKDIR texta/
CMD bash -c "python manage.py makemigrations; python manage.py migrate;  echo \"from django.contrib.auth.models import User; User.objects.create_superuser('admin', 'admin@example.com', 'pass')\" | python manage.py shell; authbind --deep python manage.py runserver 0.0.0.0:80"