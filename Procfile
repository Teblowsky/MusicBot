web: gunicorn admin:app --bind 0.0.0.0:$PORT --workers 4 --timeout 120 --log-level info
worker: python3 bot.py 2>&1 | tee -a /tmp/bot.log 