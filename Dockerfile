FROM debian:stretch
ENV PYTHONUNBUFFERED 1

RUN set -x \
    && apt-get update \
    && apt-get upgrade -y \
    && apt-get autoremove --purge \
    && apt-get autoclean \
    && apt-get install -y --no-install-recommends locales supervisor ssh ca-certificates wget bzip2 redis-server nginx-light curl nano gcc python-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
# Generate locale
    && sed -i 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen \
    && locale-gen en_US.UTF-8

WORKDIR /var

# Download and install Miniconda
RUN wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh \
    && sh Miniconda3-latest-Linux-x86_64.sh -b -p /var/miniconda3 \
    && rm Miniconda3-latest-Linux-x86_64.sh

# Create and activate Conda env
COPY environment.yaml /var/environment.yaml
RUN /var/miniconda3/bin/conda env create -f /var/environment.yaml

COPY . /var/texta-rest

# System configuration files
COPY docker-conf/uwsgi.ini /etc/uwsgi/uwsgi.ini
COPY docker-conf/nginx.conf /etc/nginx/conf.d/nginx.conf
COPY docker-conf/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Ownership to www-data and entrypoint
RUN chown -R www-data:www-data /var/texta-rest \
    && chmod 775 -R /var/texta-rest \
    && chmod +x /var/texta-rest/docker-conf/entrypoint.sh \
# Final cleanup
    && rm -rf /root/.cache

WORKDIR /var/texta-rest

ENV PYTHONIOENCODING=UTF-8
ENV UWSGI_INI /var/texta-rest/docker-conf/texta-rest.ini
# By default, run 2 processes
ENV UWSGI_CHEAPER 2
# By default, when on demand, run up to 16 processes
ENV UWSGI_PROCESSES 16
# By default, allow unlimited file sizes, modify it to limit the file sizes
# To have a maximum of 1 MB (Nginx's default) change the line to:
# ENV NGINX_MAX_UPLOAD 1m
ENV NGINX_MAX_UPLOAD 0
# By default, Nginx will run a single worker process, setting it to auto
# will create a worker for each CPU core
ENV NGINX_WORKER_PROCESSES auto

EXPOSE 80
EXPOSE 8000
EXPOSE 8001

ENTRYPOINT ["/var/texta-rest/docker-conf/entrypoint.sh"]
CMD ["/usr/bin/supervisord", "-n"]
