#!/bin/bash

# SET SOME DEFAULT VALUES IF VARIABLES NOT DEFINED
export TEXTA_SHORT_TASK_WORKERS="${TEXTA_SHORT_TASK_WORKERS:-1}"
export TEXTA_LONG_TASK_WORKERS="${TEXTA_LONG_TASK_WORKERS:-4}"
export TEXTA_MLP_TASK_WORKERS="${TEXTA_MLP_TASK_WORKERS:-2}"
export TEXTA_SHORT_MAX_TASKS="${TEXTA_SHORT_MAX_TASKS:-100}"
export TEXTA_LONG_MAX_TASKS="${TEXTA_LONG_MAX_TASKS:-1}"
export TEXTA_MLP_MAX_TASKS="${TEXTA_MLP_MAX_TASKS:-10}"
export TEXTA_CELERY_LOG_LEVEL="${TEXTA_CELERY_LOG_LEVEL:-warning}"
export TEXTA_BEAT_LOG_LEVEL="${TEXTA_BEAT_LOG_LEVEL:-warning}"

# NGINX CONF
sed -i "s/.*user .*www-data;.*/user www-data www-data;/" /opt/conda/envs/texta-rest/etc/nginx/nginx.conf
sed -i "s/^error_log .*;/error_log stderr warn;/" /opt/conda/envs/texta-rest/etc/nginx/nginx.conf
chown -R www-data /opt/conda/envs/texta-rest/var/tmp/nginx
chown -R www-data /opt/conda/envs/texta-rest/var/log/nginx

# ACTIVATE & MIGRATE
source activate texta-rest && \
  python3 migrate.py -o && \
  # prepare front conf file
  python3 create_front_conf.py > /var/texta-rest/front/assets/config/config.json

# OWNERSHIP TO WWW-DATA
chown www-data:www-data -R /var/texta-rest/static/ && chmod 777 -R /var/texta-rest/static/
chown www-data:www-data -R /var/texta-rest/data/ && chmod 777 -R /var/texta-rest/data/

exec "$@"
