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

EXPOSE 9200

USER texta
WORKDIR /home/texta

CMD elasticsearch/bin/elasticsearch