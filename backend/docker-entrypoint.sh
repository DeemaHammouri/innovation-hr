#!/bin/sh
# Starts as root only to hand the upload folder to the app user, then drops to that user for the real command.
# Needed on hosts that mount a volume or disk owned by root (Render persistent disks); with a Docker named volume it changes nothing.
set -e
if [ "$(id -u)" = "0" ]; then
  mkdir -p "${PRIVATE_MEDIA_ROOT:-/data/private_media}"
  chown app:app "${PRIVATE_MEDIA_ROOT:-/data/private_media}"
  export HOME=/home/app
  exec setpriv --reuid=app --regid=app --init-groups "$@"
fi
exec "$@"
