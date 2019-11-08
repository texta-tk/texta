FROM continuumio/miniconda3:latest

# Copy environment file
COPY environment-nomkl.yaml /var/environment.yaml


RUN set -x \
    && conda env create -f /var/environment.yaml \
    && conda clean -afy \
    && find /opt/conda/ -follow -type f -name '*.a' -delete \
    && find /opt/conda/ -follow -type f -name '*.pyc' -delete \
    && find /opt/conda/ -follow -type f -name '*.js.map' -delete



# Copy project files
COPY . /var/texta-rest

# Ownership to www-data and entrypoint
RUN chown -R www-data:www-data /var/texta-rest \
    && chmod 775 -R /var/texta-rest \
    && chmod 777 -R /opt/conda/envs/texta-rest/var \
    && chmod +x /var/texta-rest/docker/conf/entrypoint.sh \
    && rm -rf /var/texta-rest/.git \
    && rm -rf /root/.cache


# System configuration files
COPY docker/conf/supervisord.conf /opt/conda/envs/texta-rest/etc/supervisord/conf.d/supervisord.conf
ENV UWSGI_INI /var/texta-rest/docker/conf/texta-rest.ini

# Set environment variables
ENV JOBLIB_MULTIPROCESSING 0
ENV PYTHONIOENCODING=UTF-8
ENV UWSGI_CHEAPER 2
ENV UWSGI_PROCESSES 16

# Expose ports
EXPOSE 80
EXPOSE 8000
EXPOSE 8001

# Ignition!
WORKDIR /var/texta-rest
ENTRYPOINT ["/var/texta-rest/docker/conf/entrypoint.sh"]
CMD ["supervisord", "-n"]
