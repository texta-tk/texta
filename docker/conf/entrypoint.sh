#!/bin/bash

export ENV_TEXTA_SHORT_TASK_WORKERS="${TEXTA_SHORT_TASK_WORKERS:-3}"
export ENV_TEXTA_LONG_TASK_WORKERS="${TEXTA_LONG_TASK_WORKERS:-5}"

source activate texta-rest && python migrate.py
source activate texta-rest && python manage.py collectstatic --noinput --clear
chown www-data:www-data -R /var/texta-rest/static/ && chmod 777 -R /var/texta-rest/static/
chown www-data:www-data -R /var/texta-rest/data/ && chmod 777 -R /var/texta-rest/data/

set | egrep "^(DJANGO|TEXTA|PYTHON|LC_|LANG)" | sed -e 's/^/export /' > .env


exec "$@"
