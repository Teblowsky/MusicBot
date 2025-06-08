# config_db.py
import psycopg2
import os
from dotenv import load_dotenv

# Ładowanie zmiennych środowiskowych z .env
load_dotenv()

def get_db_connection():
    """Funkcja zwracająca połączenie z bazą danych PostgreSQL"""
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),  # Dodany brakujący przecinek
            port=os.getenv('DB_PORT')  # Port jako opcjonalny parametr
        )
        return conn
    except Exception as e:
        print(f"Błąd połączenia z bazą danych: {e}")
        return None
