web: . /app/venv/bin/activate && gunicorn admin:app --bind 0.0.0.0:$PORT --workers 4
worker: . /app/venv/bin/activate && python3 bot.py 