#!/usr/bin/env bash

elasticsearch/bin/elasticsearch &
cd texta
python manage.py runserver