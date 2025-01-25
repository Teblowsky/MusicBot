from flask import Flask, request, jsonify, session, redirect, url_for, render_template
from flask_discord import DiscordOAuth2Session, requires_authorization, Unauthorized
from datetime import datetime, timedelta
import os
from config_db import get_db_connection  # Importujemy funkcję połączenia z bazą danych

# Flask app initialization
app = Flask(__name__)
app.secret_key = "your_secret_key"  # Ustaw odpowiednią wartość dla secret_key
app.config["DISCORD_CLIENT_ID"] = "your_discord_client_id"
app.config["DISCORD_CLIENT_SECRET"] = "your_discord_client_secret"
app.config["DISCORD_REDIRECT_URI"] = "your_redirect_uri"
app.config["DISCORD_BOT_TOKEN"] = "your_discord_bot_token"
ADMIN_ID = 1090349769450340443  # Bezpośrednia wartość ADMIN_ID

discord = DiscordOAuth2Session(app)

# Funkcja do tworzenia tabeli w bazie (na początku, jeśli nie istnieje)
def create_tables():
    """Create the subscriptions table if it doesn't exist."""
    conn = get_db_connection()
    if conn is None:
        return  # Zakończ, jeśli połączenie z bazą się nie powiodło
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS subscriptions (
                user_id TEXT PRIMARY KEY,
                expires_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                subscription_type TEXT DEFAULT 'monthly',
                last_payment_amount DECIMAL(10, 2)
            )
            """
        )
        conn.commit()
    except Exception as e:
        print(f"Error creating tables: {e}")
    finally:
        conn.close()

# Sprawdzenie, czy użytkownik ma aktywną subskrypcję
def is_subscribed(user_id):
    """Check if a user has an active subscription."""
    conn = get_db_connection()
    if conn is None:
        return False  # Zwróć False, jeśli połączenie z bazą się nie powiodło
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

# Dodanie lub zaktualizowanie subskrypcji użytkownika
def add_subscription(user_id, days=30, subscription_type="monthly", last_payment_amount=10.00):
    """Add or update a user's subscription."""
    conn = get_db_connection()
    if conn is None:
        return  # Zakończ, jeśli połączenie z bazą nie powiodło się
    cursor = conn.cursor()
    expires_at = datetime.now() + timedelta(days=days)
    cursor.execute(
        """
        INSERT INTO subscriptions (user_id, expires_at, subscription_type, last_payment_amount)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT(user_id)
        DO UPDATE SET expires_at = %s, subscription_type = %s, last_payment_amount = %s
        """,
        (
            user_id,
            expires_at.strftime("%Y-%m-%d %H:%M:%S"),
            subscription_type,
            last_payment_amount,
            expires_at.strftime("%Y-%m-%d %H:%M:%S"),
            subscription_type,
            last_payment_amount
        ),
    )
    conn.commit()
    conn.close()

# Routes
@app.route("/login/")
def login():
    """Login route to start Discord OAuth2."""
    return discord.create_session(scope=["identify", "email"])

@app.route("/callback/") 
def callback():
    """Handle Discord OAuth2 callback."""
    try:
        discord.callback()
        user = discord.fetch_user()
        session["user_id"] = user.id
        return redirect(url_for("dashboard"))
    except Exception as e:
        return jsonify(error="Błąd logowania: " + str(e)), 400

@app.route("/logout/")
def logout():
    """Logout the user and clear the session."""
    discord.revoke()
    session.clear()
    return redirect(url_for("index"))

@app.route("/dashboard/")
@requires_authorization
def dashboard():
    """Dashboard for both users and admins."""
    user = discord.fetch_user()
    is_admin = user.id == ADMIN_ID  # Bezpośrednie przypisanie ADMIN_ID
    
    if is_admin:
        # Admin view
        conn = get_db_connection()
        if conn is None:
            return jsonify(error="Błąd połączenia z bazą danych"), 500
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
        return render_template("admin_dashboard.html", subscriptions=subscriptions, user=user)
    else:
        # User view
        active_subscription = is_subscribed(user.id)
        return render_template("user_dashboard.html", user=user, subscribed=active_subscription)

# Nowa trasa, która przekierowuje użytkownika na Patronite
@app.route("/redirect-to-patronite", methods=["POST"])
def redirect_to_patronite():
    patronite_url = "https://patronite.pl/Beazzy"  # Zmień na swój link Patronite
    return redirect(patronite_url)

# Error handling
@app.errorhandler(Unauthorized)
def unauthorized(e):
    return redirect(url_for("login"))

if __name__ == "__main__":
    create_tables()  # Tworzymy tabelę przy starcie aplikacji
    app.run(port=4242, debug=True)
