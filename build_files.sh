#!/bin/bash
set -e
echo "BUILD START"
python -m pip install -r requirements.txt --break-system-packages
python manage.py collectstatic --noinput --clear
echo "BUILD END"