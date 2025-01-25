import sqlite3
from datetime import datetime

def is_subscribed(user_id):
    conn = sqlite3.connect("subscriptions.db")
    cursor = conn.cursor()
    cursor.execute("SELECT expires_at FROM subscriptions WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        expires_at = datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S")
        return expires_at > datetime.now()
    return False
