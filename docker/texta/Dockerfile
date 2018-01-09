FROM openjdk:8-jre

RUN wget https://download.elastic.co/elasticsearch/release/org/elasticsearch/distribution/tar/elasticsearch/2.4.6/elasticsearch-2.4.6.tar.gz
RUN tar -xvf elasticsearch-2.4.6.tar.gz
RUN rm elasticsearch-2.4.6.tar.gz

ENV PATH elasticsearch-2.4.6/bin:$PATH
# ES_HEAP_SIZE should be half the available RAM
ENV ES_HEAP_SIZE 4g

ADD elasticsearch.yml elasticsearch-2.4.6/config

RUN mkdir -p /usr/share/elasticsearch/data

VOLUME /usr/share/elasticsearch/data

#RUN set -x \
#        && apt-get update \
#        && apt-get install -y --no-install-recommends \
#         git python-dev build-essential manpages-dev libblas-dev liblapack-dev libatlas-base-dev gfortran

RUN set -x \
    && apt-get update \
    && apt-get install -y --no-install-recommends python python-dev git python-pip

RUN git clone https://github.com/texta-tk/texta.git
RUN git checkout ekt-polishing-dev

WORKDIR texta

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

RUN python migrate.py

ADD run_elastic_and_texta.sh .

EXPOSE 8000 9200

CMD ["python", "manage.py", "runserver"]
