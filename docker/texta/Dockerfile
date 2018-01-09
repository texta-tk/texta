FROM openjdk:8-jre

RUN adduser --disabled-password --gecos '' texta

RUN wget https://download.elastic.co/elasticsearch/release/org/elasticsearch/distribution/tar/elasticsearch/2.4.6/elasticsearch-2.4.6.tar.gz
RUN tar -xvf elasticsearch-2.4.6.tar.gz
RUN rm elasticsearch-2.4.6.tar.gz

# ES_HEAP_SIZE should be half the available RAM
ENV ES_HEAP_SIZE 4g

ADD elasticsearch.yml elasticsearch-2.4.6/config

RUN mv elasticsearch-2.4.6 /home/texta/elasticsearch

RUN mkdir -p /usr/share/elasticsearch/data

RUN chown texta:texta /usr/share/elasticsearch/data
RUN chown -R texta:texta /home/texta/elasticsearch

VOLUME /usr/share/elasticsearch/data

#RUN set -x \
#        && apt-get update \
#        && apt-get install -y --no-install-recommends \
#         git python-dev build-essential manpages-dev libblas-dev liblapack-dev libatlas-base-dev gfortran

RUN set -x \
    && apt-get update \
    && apt-get install -y --no-install-recommends python python-dev git python-pip

RUN git clone https://github.com/texta-tk/texta.git

WORKDIR texta

RUN git checkout ekt-polishing-dev

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

WORKDIR ..

RUN mv texta /home/texta
RUN chown -R texta:texta /home/texta/texta

ADD run_elastic_and_texta.sh /home/texta
RUN chown texta:texta /home/texta/run_elastic_and_texta.sh
RUN chmod u+x /home/texta/run_elastic_and_texta.sh

RUN ls -l /home/texta

USER texta
WORKDIR /home/texta

EXPOSE 8000 9200

CMD ./run_elastic_and_texta.sh
