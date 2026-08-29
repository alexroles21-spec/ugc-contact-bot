import sqlite3
import requests
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import os

DB_FILE = "stores_database.db"

# سيرفر مصغر باش Render ما يطفيس السكربت ويعتبره شغال
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running successfully!")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    server.serve_forever()

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_name TEXT,
            store_url TEXT UNIQUE,
            contact_url TEXT,
            email TEXT,
            niche TEXT,
            country TEXT,
            status TEXT DEFAULT 'PENDING',
            created_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

def fetch_shopify_stores():
    proxy_api = "https://smart-proxy-server.onrender.com/api?key"
    try:
        response = requests.get(proxy_api, timeout=30)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Proxy Connection Error: {e}")
    return []

def filter_and_save_stores(stores):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    added_count = 0
    for store in stores:
        url = store.get("url")
        email = store.get("email")
        niche = store.get("niche", "general").lower()
        country = store.get("country", "").upper()
        name = store.get("name", "Store")
        
        contact_url = f"{url.rstrip('/')}/pages/contact"
        if not url:
            continue
            
        try:
            cursor.execute('''
                INSERT INTO stores (store_name, store_url, contact_url, email, niche, country, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (name, url, contact_url, email, niche, country, datetime.now().strftime("%Y-%m-%d")))
            conn.commit()
            added_count += 1
        except sqlite3.IntegrityError:
            pass
            
    conn.close()
    print(f"Successfully added {added_count} new unique stores.")

def generate_contact_message(store_name, niche):
    return f"""Hi {store_name} Team,

I was browsing your store and noticed your great collection in the {niche} niche. I tried reaching out via direct email, but left this here since contact forms are monitored closely.

Scaling a modern e-commerce brand in the {niche} space requires a constant stream of high-converting video ads, but traditional UGC agencies are too slow and expensive. We built an AI engine that generates hyper-realistic video ads and viral UGC formats specifically tailored for {niche} products in under a minute, using elite AI avatars and any language you need.

Top stores in your sector are using this to scale their ROAS on TikTok and Meta without handling shipping samples or hiring creators.

To see how this can instantly transform {store_name} and multiply your sales, click or copy and paste the link below into your browser:

https://ugc-gen-ai.carrd.co

Best regards,
Growth Team"""

def submit_contact_form(contact_url, sender_email, store_name, message):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        page_check = requests.get(contact_url, headers=headers, timeout=10)
        if page_check.status_code != 200 or "cloudflare" in page_check.text.lower() or "recaptcha" in page_check.text.lower():
            return False, "Protected or Captcha detected"

        payload = {
            "form_type": "contact",
            "utf8": "✓",
            "contact[name]": f"{store_name} Growth Partner",
            "contact[email]": sender_email,
            "contact[body]": message
        }
        
        response = requests.post(contact_url, data=payload, headers=headers, timeout=15, allow_redirects=True)
        
        if response.status_code == 200 and "captcha" not in response.text.lower():
            return True, "Success"
        else:
            return False, "Blocked or Form structure mismatch"
            
    except Exception as e:
        return False, str(e)

def run_automation_engine():
    init_db()
    while True:
        raw_stores = fetch_shopify_stores()
        if raw_stores:
            filter_and_save_stores(raw_stores)
            
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT id, store_name, contact_url, email, niche FROM stores WHERE status = 'PENDING'")
        pending_stores = cursor.fetchall()
        
        sender_email = "support@ugc-gen-ai.carrd.co"
        
        for store_id, store_name, contact_url, store_email, niche in pending_stores:
            message = generate_contact_message(store_name, niche)
            success, reason = submit_contact_form(contact_url, sender_email, store_name, message)
            
            if success:
                cursor.execute("UPDATE stores SET status = 'SENT' WHERE id = ?", (store_id,))
                conn.commit()
                print(f"Sent: {store_name}")
            else:
                status_label = 'SKIPPED_PROTECTED' if 'Protected' in reason else 'FAILED'
                cursor.execute("UPDATE stores SET status = ? WHERE id = ?", (status_label, store_id,))
                conn.commit()
                
            time.sleep(0.5)
            
        conn.close()
        time.sleep(60) # الإنتظار دقيقة قبل جلب دفعة جديدة

if __name__ == "__main__":
    # تشغيل سيرفر الويب في خلفية الكود باش Render يبقى راضي وما يطفيهوش
    server_thread = threading.Thread(target=run_web_server)
    server_thread.daemon = True
    server_thread.start()
    
    # تشغيل بوت الإرسال
    run_automation_engine()
