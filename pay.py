from flask import Flask, request, jsonify, session, redirect, url_for, render_template
from flask_discord import DiscordOAuth2Session, requires_authorization, Unauthorized
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv  # Importujemy bibliotekę dotenv
from config_db import get_db_connection  # Importujemy funkcję połączenia z bazą danych
from urllib.parse import quote

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Załaduj zmienne środowiskowe z pliku .env
load_dotenv()

# Flask app initialization
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")  # Pobierz secret_key z pliku .env
app.config["DISCORD_CLIENT_ID"] = os.getenv("DISCORD_CLIENT_ID")  # Pobierz CLIENT_ID
app.config["DISCORD_CLIENT_SECRET"] = os.getenv("DISCORD_CLIENT_SECRET")  # Pobierz CLIENT_SECRET
app.config["DISCORD_REDIRECT_URI"] = os.getenv("DISCORD_REDIRECT_URI")  # Pobierz REDIRECT_URI
app.config["DISCORD_BOT_TOKEN"] = os.getenv("DISCORD_BOT_TOKEN")  # Pobierz BOT_TOKEN
ADMIN_ID = int(os.getenv("ADMIN_ID", 1090349769450340443))  # Pobierz ADMIN_ID lub użyj wartości domyślnej

print("Registered Routes:")
for rule in app.url_map.iter_rules():
    print(f"{rule.endpoint} -> {rule}")
    
from config_db import get_db_connection

conn = get_db_connection()
if conn:
    print("Połączenie z bazą danych działa!")
    conn.close()
else:
    print("Błąd połączenia z bazą danych!")


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
@app.route("/")
def index():
    return render_template("index.html")  # Zmienna, zależna od tego, co chcesz wyświetlić na głównej stronie

@app.route("/login/")
def login():
    """Login route to start Discord OAuth2."""
    redirect_uri = quote("http://localhost:3000/callback")  # Korzystamy z wartości z pliku .env
    return redirect(f"https://discord.com/oauth2/authorize?client_id={app.config['DISCORD_CLIENT_ID']}&response_type=code&redirect_uri={quote(redirect_uri)}&scope=identify+email")


@app.route("/callback", methods=["GET"])
@app.route("/callback/", methods=["GET"])
def callback():
    """Handle Discord OAuth2 callback."""
    try:
        discord.callback()  # Discord callback, przetwarza kod autoryzacji
        user = discord.fetch_user()  # Pobierz dane użytkownika z Discorda
        session["user_id"] = user.id  # Zapisz ID użytkownika w sesji
        return redirect("/dashboard/")  # Po pomyślnym zalogowaniu, przekierowanie na stronę dashboard
    except Exception as e:
        print(f"Błąd logowania: {e}")  # Dodatkowe logowanie błędów
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

@app.route('/favicon.ico')
def favicon():
    return '', 204  # Odpowiada pustą odpowiedzią i kodem 204 (No Content)

if __name__ == "__main__":
    create_tables()  # Tworzy tabele przy starcie aplikacji
    app.run(host="localhost", port=3000, debug=True)