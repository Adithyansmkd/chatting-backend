#!/usr/bin/env bash
# Exit on error
set -o errexit

# Install dependencies (ensure they are installed before any django command)
pip install -r requirements.txt

# Run migrations first (safest)
python manage.py migrate

# Collect static files
python manage.py collectstatic --no-input
