#!/bin/sh
set -e

# Wait for DB if needed (simple wait loop)
if [ -n "$DB_HOST" ]; then
  echo "Waiting for database at $DB_HOST:$DB_PORT..."
  until nc -z "$DB_HOST" "$DB_PORT"; do
    echo "   still waiting for db..."
    sleep 1
  done
fi

echo "Running migrations..."
python manage.py migrate --noinput

echo "Ensuring demo accounts exist..."
python manage.py create_demo_classroom || echo "Demo seed skipped (non-fatal)"

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting Gunicorn..."
exec gunicorn teachly.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --log-level info
