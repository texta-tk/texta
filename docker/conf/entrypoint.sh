#!/bin/bash

source activate texta-rest && python migrate.py
source activate texta-rest && python manage.py collectstatic --noinput --clear
chown www-data:www-data -R /var/texta-rest/static/ && chmod 777 -R /var/texta-rest/static/
chown www-data:www-data -R /var/texta-rest/data/ && chmod 777 -R /var/texta-rest/data/

set | egrep "^(DJANGO|TEXTA|PYTHON|LC_|LANG)" | sed -e 's/^/export /' > .env

exec "$@"
