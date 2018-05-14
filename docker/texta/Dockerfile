FROM ubuntu:latest

ENV LANG C.UTF-8

RUN adduser --disabled-password --gecos '' texta

#RUN set -x \
#        && apt-get update \
#        && apt-get install -y --no-install-recommends \
#         git python-dev build-essential manpages-dev libblas-dev liblapack-dev libatlas-base-dev gfortran

RUN set -x \
    && apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-dev git python3-pip swig gcc libpulse-dev

RUN apt-get install -y curl
RUN apt-get install -y authbind
RUN touch /etc/authbind/byport/80
RUN chmod 777 /etc/authbind/byport/80

RUN pip3 install --upgrade pip

RUN pip3 install setuptools
RUN pip3 install wheel
RUN pip3 install requests
RUN pip3 install numpy
RUN pip3 install cython
RUN pip3 install scipy
RUN pip3 install sklearn
RUN pip3 install gensim
RUN pip3 install django==2.0.2
RUN pip3 install pathlib
RUN pip3 install dateutils
RUN pip3 install sympy
RUN pip3 install textract

RUN git clone https://github.com/texta-tk/texta.git
WORKDIR texta
RUN git checkout dev
RUN python3 migrate.py

RUN echo "from django.contrib.auth.models import User; User.objects.create_superuser('admin', 'admin@example.com', '1234')" | python3 manage.py shell

WORKDIR ..

RUN mv texta /home/texta
RUN chown -R texta:texta /home/texta/texta

EXPOSE 80

USER texta
WORKDIR /home/texta/texta

ADD settings.py texta

CMD ["authbind", "--deep", "python3", "manage.py", "runserver", "0.0.0.0:80"]