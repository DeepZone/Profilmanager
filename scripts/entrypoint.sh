#!/usr/bin/env bash
set -e

flask --app manage.py db upgrade
flask --app manage.py seed-admin
exec gunicorn -w 2 -b 0.0.0.0:5000 run:app
