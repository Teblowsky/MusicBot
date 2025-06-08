FROM openjdk:17-slim

WORKDIR /app

# Instalacja FFmpeg i innych zależności
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Pobranie Lavalink
RUN wget https://github.com/lavalink-devs/Lavalink/releases/download/4/application.yml -O application.yml && \
    wget https://github.com/lavalink-devs/Lavalink/releases/download/4/Lavalink.jar -O Lavalink.jar

# Instalacja Pythona i zależności
RUN apt-get update && \
    apt-get install -y python3 python3-pip && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Kopiowanie plików projektu
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

# Uruchomienie Lavalink i bota
CMD java -jar Lavalink.jar & python3 bot.py 