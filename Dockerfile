FROM python:3.12-slim

WORKDIR /app

# Instalacja FFmpeg i innych zależności
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Kopiowanie plików projektu
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Uruchomienie bota
CMD ["python", "bot.py"] 