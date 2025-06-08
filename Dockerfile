FROM python:3.11-slim

WORKDIR /app

# Instalacja zależności systemowych
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Kopiowanie plików projektu
COPY requirements.txt .
COPY . .

# Instalacja zależności Pythona
RUN pip install --no-cache-dir -r requirements.txt

# Ustawienie zmiennych środowiskowych
ENV PYTHONUNBUFFERED=1
ENV PORT=3000

# Ekspozycja portu
EXPOSE 3000

# Uruchomienie aplikacji
CMD ["gunicorn", "admin:app", "--bind", "0.0.0.0:3000", "--workers", "4", "--timeout", "120"] 