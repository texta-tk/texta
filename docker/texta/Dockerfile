FROM ubuntu:latest

RUN adduser --disabled-password --gecos '' texta

#RUN set -x \
#        && apt-get update \
#        && apt-get install -y --no-install-recommends \
#         git python-dev build-essential manpages-dev libblas-dev liblapack-dev libatlas-base-dev gfortran

RUN set -x \
    && apt-get update \
    && apt-get install -y --no-install-recommends python python-dev git python-pip swig gcc libpulse-dev

RUN git clone https://github.com/texta-tk/texta.git

WORKDIR texta

RUN git checkout ekt-polishing-dev

RUN pip install --upgrade pip

RUN pip install setuptools
RUN pip install wheel
RUN pip install requests
RUN pip install numpy
RUN pip install cython
RUN pip install scipy
RUN pip install sklearn
RUN pip install gensim
RUN pip install django==1.11
RUN pip install pathlib
RUN pip install dateutils
RUN pip install sympy
RUN pip install textract

RUN python migrate.py

RUN echo "from django.contrib.auth.models import User; User.objects.create_superuser('admin', 'admin@example.com', '1234')" | python manage.py shell

WORKDIR ..

RUN mv texta /home/texta
RUN chown -R texta:texta /home/texta/texta

RUN apt-get install -y curl

EXPOSE 80

RUN apt-get install -y authbind
RUN touch /etc/authbind/byport/80
RUN chmod 777 /etc/authbind/byport/80

USER texta
WORKDIR /home/texta/texta

ADD settings.py texta

CMD ["authbind", "--deep", "python", "manage.py", "runserver", "0.0.0.0:80"]