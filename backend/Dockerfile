FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --create-home app && mkdir -p /data/private_media /app/cache && chown -R app /data /app/cache && chmod +x /app/docker-entrypoint.sh
# Runs as root only long enough to fix the ownership of the mounted upload folder, then the entrypoint drops to the app user.
ENV DJANGO_SETTINGS_MODULE=config.settings.production PRIVATE_MEDIA_ROOT=/data/private_media
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --retries=5 CMD python -c "import os,sys,urllib.request as u; r=u.Request('http://127.0.0.1:8000/api/v1/health/', headers={'Host': os.environ['DJANGO_ALLOWED_HOSTS'].split(',')[0].strip()}); sys.exit(0 if u.urlopen(r, timeout=4).status==200 else 1)"
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --access-logfile -"]
