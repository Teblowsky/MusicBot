# config_db.py
import psycopg2
import os
from dotenv import load_dotenv
import logging

# Konfiguracja logowania
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ładowanie zmiennych środowiskowych z .env
load_dotenv()

def get_db_connection():
    """Funkcja zwracająca połączenie z bazą danych PostgreSQL"""
    try:
        # Pobierz zmienne środowiskowe z Railway
        db_url = os.getenv('DATABASE_URL')
        if db_url:
            # Parse URL połączenia
            conn = psycopg2.connect(db_url)
        else:
            # Fallback do pojedynczych zmiennych
            conn = psycopg2.connect(
                host=os.getenv("DB_HOST", "localhost"),
                database=os.getenv("DB_NAME", "postgres"),
                user=os.getenv("DB_USER", "postgres"),
                password=os.getenv("DB_PASSWORD", ""),
                port=int(os.getenv("DB_PORT", "5432"))
            )
        logger.info("Połączenie z bazą danych udane")
        return conn
    except Exception as e:
        logger.error(f"Błąd połączenia z bazą danych: {e}")
        return None
