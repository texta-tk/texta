#!/bin/bash

# SET SOME DEFAULT VALUES IF VARIABLES NOT DEFINED
export TEXTA_SHORT_TASK_WORKERS="${TEXTA_SHORT_TASK_WORKERS:-1}"
export TEXTA_LONG_TASK_WORKERS="${TEXTA_LONG_TASK_WORKERS:-4}"
export TEXTA_MLP_TASK_WORKERS="${TEXTA_MLP_TASK_WORKERS:-2}"

export TEXTA_SHORT_MAX_TASKS="${TEXTA_SHORT_MAX_TASKS:-100}"
export TEXTA_LONG_MAX_TASKS="${TEXTA_SHORT_LONG_TASKS:-10}"

export TEXTA_USE_UAA="${TEXTA_USE_UAA:-false}"
export TEXTA_API_URL="${TEXTA_API_URL:-http://localhost}"

export TEXTA_HOSTED_FILE_FIELD="${TEXTA_HOSTED_FILE_FIELD:-properties.hosted_filepath}"
sed -i "s#TEXTA_HOSTED_FILE_FIELD_REPLACE#$TEXTA_HOSTED_FILE_FIELD#g" /var/texta-rest/front/main*.js

# REST API LOCATION
sed -i "s#TEXTA_API_URL_REPLACE#$TEXTA_API_URL#g" /var/texta-rest/front/main*.js
# UAA SETTINGS
sed -i "s#TEXTA_USE_UAA_REPLACE#$TEXTA_USE_UAA#g" /var/texta-rest/front/main*.js
sed -i "s#TEXTA_UAA_URL_REPLACE#$TEXTA_UAA_URL#g" /var/texta-rest/front/main*.js
sed -i "s#TEXTA_UAA_REDIRECT_URI_REPLACE#$TEXTA_UAA_REDIRECT_URI#g" /var/texta-rest/front/main*.js
sed -i "s#TEXTA_UAA_CLIENT_ID_REPLACE#$TEXTA_UAA_CLIENT_ID#g" /var/texta-rest/front/main*.js
# NGINX CONF
sed -i "s/.*user .*www-data;.*/user www-data www-data;/" /opt/conda/envs/texta-rest/etc/nginx/nginx.conf
sed -i "s/^error_log .*;/error_log stderr warn;/" /opt/conda/envs/texta-rest/etc/nginx/nginx.conf
chown -R www-data /opt/conda/envs/texta-rest/var/tmp/nginx
chown -R www-data /opt/conda/envs/texta-rest/var/log/nginx
# ACTIVATE & MIGRATE
source activate texta-rest && \
  python3 migrate.py -o
# OWNERSHIP TO WWW-DATA
chown www-data:www-data -R /var/texta-rest/static/ && chmod 777 -R /var/texta-rest/static/
chown www-data:www-data -R /var/texta-rest/data/ && chmod 777 -R /var/texta-rest/data/

exec "$@"
