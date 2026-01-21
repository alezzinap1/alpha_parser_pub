#!/usr/bin/env sh
set -e
mkdir -p /data

if [ -f /data/CONFIG.py ]; then ln -sf /data/CONFIG.py /app/src/CONFIG.py; fi
[ -f /data/channels_v2.db ] || touch /data/channels_v2.db
ln -sf /data/channels_v2.db /app/channels_v2.db
for s in userbot2_session.session userbot_session.session; do
  if [ -f /data/$s ]; then ln -sf /data/$s /app/$s; fi
done
exec python -u -m src.RUN4
