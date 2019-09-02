# We use nvidia cuda image ase base like in this tensorflow solution:
# https://github.com/tensorflow/tensorflow/tree/master/tensorflow/tools/dockerfiles/dockerfiles

ARG CUDA=10.0
FROM nvidia/cuda:${CUDA}-base-ubuntu18.04

# ARCH and CUDA are specified again because the FROM directive resets ARGs
# (but their default value is retained if set previously)
ARG CUDNN=7.6.2.24-1
ARG CUDA

SHELL ["/bin/bash", "-c"]

# Install Tensorflow dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        cuda-command-line-tools-${CUDA/./-} \
        cuda-cublas-${CUDA/./-} \
        cuda-cufft-${CUDA/./-} \
        cuda-curand-${CUDA/./-} \
        cuda-cusolver-${CUDA/./-} \
        cuda-cusparse-${CUDA/./-} \
        curl \
        libcudnn7=${CUDNN}+cuda${CUDA} \
        libfreetype6-dev \
        libhdf5-serial-dev \
        libzmq3-dev \
        wget

# For CUDA profiling, TensorFlow requires CUPTI.
ENV LD_LIBRARY_PATH /usr/local/cuda/extras/CUPTI/lib64:/usr/local/cuda/lib64:$LD_LIBRARY_PATH

# Link the libcuda stub to the location where tensorflow is searching for it and reconfigure
# dynamic linker run-time bindings
RUN ln -s /usr/local/cuda/lib64/stubs/libcuda.so /usr/local/cuda/lib64/stubs/libcuda.so.1 \
    && echo "/usr/local/cuda/lib64/stubs" > /etc/ld.so.conf.d/z-cuda-stubs.conf \
    && ldconfig

# Download and install Miniconda
RUN wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh
RUN sh Miniconda3-latest-Linux-x86_64.sh -b -p /opt/conda && rm Miniconda3-latest-Linux-x86_64.sh

# Add conda binaries to path
ENV PATH /opt/conda/bin:$PATH

# Create and activate Conda env
COPY environment.yaml /var/environment.yaml
RUN conda env create -f /var/environment.yaml
ENV PATH /var/miniconda3/envs/texta-rest/bin:$PATH

# clean conda
RUN conda clean --all -y

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
