#!/bin/bash

# SET SOME DEFAULT VALUES IF VARIABLES NOT DEFINED
export TEXTA_SHORT_TASK_WORKERS="${TEXTA_SHORT_TASK_WORKERS:-3}"
export TEXTA_LONG_TASK_WORKERS="${TEXTA_LONG_TASK_WORKERS:-5}"
export TEXTA_MLP_TASK_WORKERS="${TEXTA_MLP_TASK_WORKERS:-2}"
export TEXTA_USE_UAA="${TEXTA_USE_UAA:-false}"

# REST API LOCATION
sed -i "s#TEXTA_API_URL_REPLACE#$TEXTA_API_URL#g" /var/texta-rest/front/main*.js
# UAA SETTINGS
sed -i "s#TEXTA_USE_UAA_REPLACE#$TEXTA_USE_UAA#g" /var/texta-rest/front/main*.js
sed -i "s#TEXTA_UAA_URL_REPLACE#$TEXTA_UAA_URL#g" /var/texta-rest/front/main*.js
sed -i "s#TEXTA_UAA_AUTH_URL_REPLACE#$TEXTA_UAA_AUTH_URL#g" /var/texta-rest/front/main*.js
sed -i "s#TEXTA_UAA_REDIRECT_URI_REPLACE#$TEXTA_UAA_REDIRECT_URI#g" /var/texta-rest/front/main*.js
sed -i "s#TEXTA_UAA_CLIENT_ID_REPLACE#$TEXTA_UAA_CLIENT_ID#g" /var/texta-rest/front/main*.js
# NGINX CONF
sed -i "s/.*user .*www-data;.*/user www-data www-data;/" /opt/conda/envs/texta-rest/etc/nginx/nginx.conf
sed -i "s/^error_log .*;/error_log stderr warn;/" /opt/conda/envs/texta-rest/etc/nginx/nginx.conf
chown -R www-data /opt/conda/envs/texta-rest/var/tmp/nginx
chown -R www-data /opt/conda/envs/texta-rest/var/log/nginx
# ACTIVATE & MIGRATE
source activate texta-rest && \
  python3 migrate.py
# OWNERSHIP TO WWW-DATA
chown www-data:www-data -R /var/texta-rest/static/ && chmod 777 -R /var/texta-rest/static/
chown www-data:www-data -R /var/texta-rest/data/ && chmod 777 -R /var/texta-rest/data/

exec "$@"
