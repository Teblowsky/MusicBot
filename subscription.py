import stripe
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from config_db import get_db_connection

load_dotenv()
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

class SubscriptionManager:
    def __init__(self):
        self.plans = {
            'basic': {
                'price_id': os.getenv('STRIPE_BASIC_PRICE_ID'),
                'max_servers': 1,
                'max_queue': 10,
                'quality': '128kbps'
            },
            'pro': {
                'price_id': os.getenv('STRIPE_PRO_PRICE_ID'),
                'max_servers': 5,
                'max_queue': 50,
                'quality': '192kbps'
            },
            'enterprise': {
                'price_id': os.getenv('STRIPE_ENTERPRISE_PRICE_ID'),
                'max_servers': float('inf'),
                'max_queue': 100,
                'quality': '320kbps'
            }
        }

    def create_checkout_session(self, user_id, plan_type):
        try:
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price': self.plans[plan_type]['price_id'],
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=f"{os.getenv('WEBSITE_URL')}/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{os.getenv('WEBSITE_URL')}/cancel",
                metadata={
                    'user_id': user_id,
                    'plan_type': plan_type
                }
            )
            return checkout_session.url
        except Exception as e:
            print(f"Błąd tworzenia sesji płatności: {e}")
            return None

    def handle_webhook(self, event):
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            user_id = session['metadata']['user_id']
            plan_type = session['metadata']['plan_type']
            
            # Aktualizuj bazę danych
            conn = get_db_connection()
            if conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO subscriptions (user_id, plan_type, status, start_date, end_date)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (user_id) DO UPDATE
                        SET plan_type = %s, status = %s, start_date = %s, end_date = %s
                    """, (
                        user_id, plan_type, 'active', 
                        datetime.now(), 
                        datetime.now() + timedelta(days=30),
                        plan_type, 'active',
                        datetime.now(),
                        datetime.now() + timedelta(days=30)
                    ))
                    conn.commit()
                finally:
                    conn.close()

    def get_user_plan(self, user_id):
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT plan_type, status, end_date 
                    FROM subscriptions 
                    WHERE user_id = %s
                """, (user_id,))
                result = cursor.fetchone()
                if result:
                    plan_type, status, end_date = result
                    if status == 'active' and end_date > datetime.now():
                        return self.plans[plan_type]
                return self.plans['basic']  # Domyślny plan
            finally:
                conn.close()
        return self.plans['basic'] 