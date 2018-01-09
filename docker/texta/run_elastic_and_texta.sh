#!/usr/bin/env bash

cd texta
elasticsearch &
python manage.py runserver