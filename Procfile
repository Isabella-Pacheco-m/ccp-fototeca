release: python manage.py migrate --noinput && python manage.py crear_superadmin --solo-si-falta
web: gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 3 --timeout 120 --access-logfile -
