#!/bin/bash

export TEXTA_SHORT_TASK_WORKERS="${TEXTA_SHORT_TASK_WORKERS:-3}"
export TEXTA_LONG_TASK_WORKERS="${TEXTA_LONG_TASK_WORKERS:-5}"
export TEXTA_MLP_TASK_WORKERS="${TEXTA_MLP_TASK_WORKERS:-2}"

sed -i "s#REST_API_URL_REPLACE#$TEXTA_API_URL#g" /var/texta-rest/front/main*.js
sed -i "s/.*user .*www-data;.*/user www-data www-data;/" /opt/conda/envs/texta-rest/etc/nginx/nginx.conf
sed -i "s/^error_log .*;/error_log stderr warn;/" /opt/conda/envs/texta-rest/etc/nginx/nginx.conf
chown -R www-data /opt/conda/envs/texta-rest/var/tmp/nginx
chown -R www-data /opt/conda/envs/texta-rest/var/log/nginx

source activate texta-rest && \
  python3 migrate.py && \
  #python3 manage.py collectstatic --noinput --clear

chown www-data:www-data -R /var/texta-rest/static/ && chmod 777 -R /var/texta-rest/static/
chown www-data:www-data -R /var/texta-rest/data/ && chmod 777 -R /var/texta-rest/data/

exec "$@"
