build:
	docker-compose build

up:
	docker-compose up -d

start:
	docker-compose start

stop:
	docker-compose stop

restart:
	docker-compose stop && docker-compose start


shell-web:
	docker exec -it texta bash

shell-db:
	docker exec -it db bash

shell-elastic:
	docker exec -u 0 -it texta-elastic bash

log-web:
	docker-compose logs -f texta

log-db:
	docker-compose logs -f db

log-compose:
	docker-compose logs -f

apply-migrations:
	docker exec -it texta-toolkit bash -c "python manage.py makemigrations"
	docker exec -it texta-toolkit bash -c "python manage.py migrate"

create-superuser:
	docker exec -it texta-toolkit bash -c "echo \"from django.contrib.auth.models import User; User.objects.create_superuser('admin', 'admin@example.com', 'pass')\" | python manage.py shell;"
