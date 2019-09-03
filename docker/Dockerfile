FROM debian:stretch

RUN set -x \
    && apt-get update \
    && apt-get autoremove --purge \
    && apt-get autoclean \
    && apt-get install -y --no-install-recommends ca-certificates wget \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Download and install Miniconda
RUN wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh
RUN sh Miniconda3-latest-Linux-x86_64.sh -b -p /opt/conda && rm Miniconda3-latest-Linux-x86_64.sh

# Add conda binaries to path
ENV PATH /opt/conda/bin:$PATH

# Create and activate Conda env
COPY environment.yaml /var/environment.yaml
RUN conda env create -f /var/environment.yaml
ENV PATH /opt/conda/envs/texta-rest/bin:$PATH

# Clean conda
RUN conda clean --all

# Copy project files
COPY . /var/texta-rest

# Ownership to www-data and entrypoint
RUN chown -R www-data:www-data /var/texta-rest \
    && chmod 775 -R /var/texta-rest \
    && chmod 777 -R /opt/conda/envs/texta-rest/var \
    && chmod +x /var/texta-rest/docker/conf/entrypoint.sh \
    && rm -rf /root/.cache

# System configuration files
COPY docker/conf/nginx.conf  /opt/conda/envs/texta-rest/etc/nginx/conf.d/nginx.conf
COPY docker/conf/supervisord.conf /opt/conda/envs/texta-rest/etc/supervisord/conf.d/supervisord.conf
ENV UWSGI_INI /var/texta-rest/docker/conf/texta-rest.ini

# Set environment variables
ENV JOBLIB_MULTIPROCESSING 0
ENV PYTHONIOENCODING=UTF-8
ENV UWSGI_CHEAPER 2
ENV UWSGI_PROCESSES 16
ENV NGINX_MAX_UPLOAD 0
ENV NGINX_WORKER_PROCESSES auto

# Expose ports
EXPOSE 80
EXPOSE 8000
EXPOSE 8001

# Ignition!
WORKDIR /var/texta-rest
ENTRYPOINT ["/var/texta-rest/docker/conf/entrypoint.sh"]
CMD ["supervisord", "-n"]