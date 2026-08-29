import sqlite3
import requests
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import os
import urllib.parse

DB_FILE = "stores_database.db"

# إحصائيات المراقبة الحية
stats = {
    "total_sent": 0,
    "total_failed": 0,
    "last_store": "None",
    "status": "Running"
}

class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>UGC Bot Live Monitor</title>
            <meta http-equiv="refresh" content="5">
            <style>
                body {{ font-family: Arial, sans-serif; background: #0f172a; color: #f8fafc; text-align: center; padding: 50px; }}
                .card {{ background: #1e293b; padding: 20px; border-radius: 12px; display: inline-block; box-shadow: 0 4px 6px rgba(0,0,0,0.3); width: 350px; }}
                h1 {{ color: #38bdf8; font-size: 22px; }}
                p {{ font-size: 18px; margin: 10px 0; }}
                .sent {{ color: #4ade80; font-weight: bold; }}
                .failed {{ color: #f87171; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="card">
                <h1>🚀 UGC Bot Live Monitor</h1>
                <p>Status: <span class="sent">{stats['status']}</span></p>
                <p>Total Sent: <span class="sent">{stats['total_sent']}</span></p>
                <p>Failed / Skipped: <span class="failed">{stats['total_failed']}</span></p>
                <p>Last Store: <br><b>{stats['last_store']}</b></p>
                <p style="font-size: 12px; color: #94a3b8; margin-top: 20px;">Auto-refreshes every 5 seconds</p>
            </div>
        </body>
        </html>
        """
        self.wfile.write(html.encode("utf-8"))

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), DashboardHandler)
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

def fetch_shopify_stores_using_proxy_key():
    # السيرفر هو لي كيدير الطلب، وكيستعمل البروكسي كمفتاح عبر بارامتر url
    proxy_base = "http://smart-proxy-server.onrender.com/proxy?key=proxy_41660a34c997820e3341be419e270edd&url="
    
    # المواقع أو المصادر المستهدفة لي غيستعمل فيها السيرفر "المفتاح" باش يجيب المتاجر بلا حظر
    target_sources = [
        "https://www.shopify.com/examples",
        "https://www.siteoscope.com/stores/shopify/"
    ]
    
    all_stores = []
    
    for target in target_sources:
        try:
            # دمج رابط المفتاح (البروكسي) مع الرابط المستهدف باش السيرفر يدوز الطلب بأمان
            final_request_url = proxy_base + urllib.parse.quote(target, safe='')
            
            response = requests.get(final_request_url, timeout=20)
            if response.status_code == 200:
                html_content = response.text
                
                import re
                found_links = re.findall(r'href=[\"\'](https?://(?:www\.)?[a-zA-Z0-9\-]+\.[a-zA-Z0-9\/]+)[\"\']', html_content)
                
                for link in set(found_links):
                    if "shopify" not in link and "google" not in link and "facebook" not in link and len(link) < 50:
                        domain_name = link.split("//")[-1].split("/")[0]
                        all_stores.append({
                            "name": domain_name.split(".")[0].capitalize(),
                            "url": link,
                            "email": f"support@{domain_name}",
                            "niche": "إلكترونيات وموضة",
                            "country": "US"
                        })
        except Exception as e:
            print(f"Fetch Error: {e}")
            
    return all_stores[:30]

def filter_and_save_stores(stores):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    added_count = 0
    for store in stores:
        url = store.get("url")
        email = store.get("email", "")
        niche = store.get("niche", "general")
        country = store.get("country", "US")
        name = store.get("name", "Store")
        
        if not url:
            continue
            
        contact_url = f"{url.rstrip('/')}/pages/contact"
            
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
    global stats
    init_db()
    while True:
        stats["status"] = "Server fetching stores using proxy key..."
        raw_stores = fetch_shopify_stores_using_proxy_key()
        if raw_stores:
            filter_and_save_stores(raw_stores)
            
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT id, store_name, contact_url, email, niche FROM stores WHERE status = 'PENDING'")
        pending_stores = cursor.fetchall()
        
        sender_email = "support@ugc-gen-ai.carrd.co"
        
        stats["status"] = "Sending messages..."
        for store_id, store_name, contact_url, store_email, niche in pending_stores:
            message = generate_contact_message(store_name, niche)
            success, reason = submit_contact_form(contact_url, sender_email, store_name, message)
            
            stats["last_store"] = store_name
            if success:
                cursor.execute("UPDATE stores SET status = 'SENT' WHERE id = ?", (store_id,))
                conn.commit()
                stats["total_sent"] += 1
                print(f"Sent: {store_name}")
            else:
                status_label = 'SKIPPED_PROTECTED' if 'Protected' in reason else 'FAILED'
                cursor.execute("UPDATE stores SET status = ? WHERE id = ?", (status_label, store_id,))
                conn.commit()
                stats["total_failed"] += 1
                
            time.sleep(0.5)
            
        conn.close()
        stats["status"] = "Waiting for new batch..."
        time.sleep(60)

if __name__ == "__main__":
    server_thread = threading.Thread(target=run_web_server)
    server_thread.daemon = True
    server_thread.start()
    
    run_automation_engine()
