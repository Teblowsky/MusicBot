from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_discord import DiscordOAuth2Session, requires_authorization
import os
from dotenv import load_dotenv
from config_db import get_db_connection
from subscription import SubscriptionManager

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY')
app.config["DISCORD_CLIENT_ID"] = os.getenv('DISCORD_CLIENT_ID')
app.config["DISCORD_CLIENT_SECRET"] = os.getenv('DISCORD_CLIENT_SECRET')
app.config["DISCORD_REDIRECT_URI"] = os.getenv('DISCORD_REDIRECT_URI')

discord = DiscordOAuth2Session(app)
subscription_manager = SubscriptionManager()

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/login")
def login():
    return discord.create_session()

@app.route("/callback")
def callback():
    discord.callback()
    return redirect(url_for("dashboard"))

@app.route("/dashboard")
@requires_authorization
def dashboard():
    user = discord.fetch_user()
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            # Pobierz serwery użytkownika
            cursor.execute("""
                SELECT s.* FROM servers s
                WHERE s.owner_id = %s
            """, (user.id,))
            servers = cursor.fetchall()
            
            # Pobierz subskrypcję
            cursor.execute("""
                SELECT * FROM subscriptions
                WHERE user_id = %s
            """, (user.id,))
            subscription = cursor.fetchone()
            
            return render_template("dashboard.html", 
                                 user=user, 
                                 servers=servers,
                                 subscription=subscription)
        finally:
            conn.close()
    return render_template("error.html", message="Błąd połączenia z bazą danych")

@app.route("/server/<int:server_id>")
@requires_authorization
def server_dashboard(server_id):
    user = discord.fetch_user()
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            # Sprawdź uprawnienia
            cursor.execute("""
                SELECT * FROM servers
                WHERE server_id = %s AND owner_id = %s
            """, (server_id, user.id))
            server = cursor.fetchone()
            
            if not server:
                return render_template("error.html", message="Brak uprawnień")
            
            # Pobierz statystyki
            cursor.execute("""
                SELECT * FROM statistics
                WHERE server_id = %s
                ORDER BY date DESC
                LIMIT 30
            """, (server_id,))
            stats = cursor.fetchall()
            
            return render_template("server.html", 
                                 user=user,
                                 server=server,
                                 stats=stats)
        finally:
            conn.close()
    return render_template("error.html", message="Błąd połączenia z bazą danych")

@app.route("/subscribe/<plan_type>")
@requires_authorization
def subscribe(plan_type):
    user = discord.fetch_user()
    checkout_url = subscription_manager.create_checkout_session(user.id, plan_type)
    if checkout_url:
        return redirect(checkout_url)
    return render_template("error.html", message="Błąd tworzenia sesji płatności")

@app.route("/webhook", methods=['POST'])
def webhook():
    event = request.json
    subscription_manager.handle_webhook(event)
    return jsonify({"status": "success"}) 