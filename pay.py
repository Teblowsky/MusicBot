from flask import Flask, request, jsonify, session, redirect, url_for, render_template
from flask_discord import DiscordOAuth2Session, requires_authorization, Unauthorized
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
from config_db import get_db_connection

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
app.config["DISCORD_CLIENT_ID"] = os.getenv("DISCORD_CLIENT_ID")
app.config["DISCORD_CLIENT_SECRET"] = os.getenv("DISCORD_CLIENT_SECRET")
app.config["DISCORD_REDIRECT_URI"] = os.getenv("DISCORD_REDIRECT_URI")
app.config["DISCORD_BOT_TOKEN"] = os.getenv("DISCORD_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))  # Dodane: pobieranie ADMIN_ID z .env

discord = DiscordOAuth2Session(app)

def create_tables():
    conn = get_db_connection()
    if conn is None:
        return
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                user_id TEXT PRIMARY KEY,
                expires_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                subscription_type TEXT DEFAULT 'monthly',
                last_payment_amount DECIMAL(10,2)
            )
        """)
        conn.commit()
    except Exception as e:
        print(f"Error creating tables: {e}")
    finally:
        conn.close()

def is_subscribed(user_id):
    conn = get_db_connection()
    if conn is None:
        return False
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT expires_at FROM subscriptions WHERE user_id = %s", (str(user_id),))
        result = cursor.fetchone()
        
        if result:
            expires_at = datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S")
            return expires_at > datetime.now()
        return False
    except Exception as e:
        print(f"Error checking subscription: {e}")
        return False
    finally:
        conn.close()

# Reszta kodu pozostaje bez zmian, ale zamień YOUR_ADMIN_ID na ADMIN_ID

@app.route("/dashboard/")
@requires_authorization
def dashboard():
    user = discord.fetch_user()
    is_admin = user.id == ADMIN_ID  # Zmienione: używamy ADMIN_ID z .env
    
    if is_admin:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    s.user_id,
                    s.expires_at,
                    s.created_at,
                    s.subscription_type,
                    s.last_payment_amount
                FROM subscriptions s
                ORDER BY s.created_at DESC
            """)
            subscriptions = cursor.fetchall()
            conn.close()
            return render_template("admin_dashboard.html", 
                                 subscriptions=subscriptions,
                                 user=user)
    
    return render_template("user_dashboard.html",
                          user=user,
                          subscribed=is_subscribed(user.id))

# Reszta kodu pozostaje bez zmian...