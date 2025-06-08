FROM python:3.11-slim

WORKDIR /app

# Instalacja zależności systemowych
RUN apt-get update && apt-get install -y \
    ffmpeg \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Kopiowanie plików projektu
COPY requirements.txt .

# Aktualizacja pip i instalacja zależności
RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Kopiowanie reszty plików
COPY . .

# Uruchomienie aplikacji
CMD ["python3", "bot.py"] 