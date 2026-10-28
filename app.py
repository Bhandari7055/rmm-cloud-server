import os
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from twilio.rest import Client

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "rmm_secret_key_12345")

# Twilio Environment Configuration (Render Variables se padhega)
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")
ADMIN_PHONE_NUMBER = "+917055361662"

DB_FILE = "rmm.db"

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            otp TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agents (
            hostname TEXT PRIMARY KEY,
            screenshot_status TEXT,
            last_seen TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hostname TEXT,
            url TEXT,
            timestamp TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS blocked_domains (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT UNIQUE
        )
    ''')
    
    cursor.execute("SELECT * FROM admin WHERE username = 'admin'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO admin (username, password) VALUES ('admin', 'admin123')")
        
    conn.commit()
    conn.close()

def auto_cleanup_90_days_history():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cutoff_date = datetime.now() - timedelta(days=90)
        cursor.execute("DELETE FROM history WHERE timestamp < ?", (cutoff_date.strftime("%Y-%m-%d %H:%M:%S"),))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[!] History Auto Cleanup Error: {e}")

init_db()

@app.route('/')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    auto_cleanup_90_days_history()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM agents")
    agents = cursor.fetchall()
    cursor.execute("SELECT * FROM blocked_domains")
    blocked = cursor.fetchall()
    conn.close()
    
    return render_template('dashboard.html', agents=agents, blocked=blocked)

@app.route('/login', methods=['GET', 'POST'])
def login():
    msg = ""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM admin WHERE username=? AND password=?", (username, password))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            msg = "Invalid Username or Password!"
            
    return render_template('login.html', msg=msg)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    msg = ""
    step = 1
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'send_otp':
            import random
            otp = str(random.randint(100000, 999999))
            
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("UPDATE admin SET otp=? WHERE username='admin'", (otp,))
            conn.commit()
            conn.close()
            
            try:
                client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
                client.messages.create(
                    body=f"Your RMM Admin Password Reset OTP is: {otp}",
                    from_=TWILIO_PHONE_NUMBER,
                    to=ADMIN_PHONE_NUMBER
                )
                msg = f"OTP sent via SMS to {ADMIN_PHONE_NUMBER}!"
                step = 2
            except Exception as e:
                msg = f"Failed to send SMS OTP: {str(e)}"
                step = 1
                
        elif action == 'verify_reset':
            user_otp = request.form.get('otp')
            new_password = request.form.get('new_password')
            
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM admin WHERE username='admin' AND otp=?", (user_otp,))
            user = cursor.fetchone()
            
            if user:
                cursor.execute("UPDATE admin SET password=?, otp=NULL WHERE username='admin'", (new_password,))
                conn.commit()
                conn.close()
                return redirect(url_for('login'))
            else:
                conn.close()
                msg = "Invalid OTP! Please try again."
                step = 2
                
    return render_template('reset_password.html', msg=msg, step=step)

@app.route('/api/system/ping', methods=['POST'])
def system_ping():
    data = request.json or {}
    hostname = data.get('hostname')
    screenshot_status = data.get('screenshot_status', 'Active')
    
    if not hostname:
        return jsonify({"status": "error", "message": "Hostname required"}), 400
        
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO agents (hostname, screenshot_status, last_seen)
        VALUES (?, ?, ?)
        ON CONFLICT(hostname) DO UPDATE SET
            screenshot_status=excluded.screenshot_status,
            last_seen=excluded.last_seen
    ''', (hostname, screenshot_status, now))
    conn.commit()
    conn.close()
    
    return jsonify({"status": "success"})

@app.route('/api/system/history', methods=['POST'])
def log_history():
    data = request.json or {}
    hostname = data.get('hostname')
    url = data.get('url')
    
    if hostname and url:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO history (hostname, url, timestamp) VALUES (?, ?, ?)", (hostname, url, now))
        conn.commit()
        conn.close()
        
        auto_cleanup_90_days_history()
        
    return jsonify({"status": "success"})

@app.route('/agent/<hostname>')
def view_agent_history(hostname):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    auto_cleanup_90_days_history()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM history WHERE hostname=? ORDER BY timestamp DESC", (hostname,))
    history_records = cursor.fetchall()
    conn.close()
    
    return render_template('agent_history.html', hostname=hostname, history=history_records)

@app.route('/block-domain', methods=['POST'])
def block_domain():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    domain = request.form.get('domain')
    if domain:
        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO blocked_domains (domain) VALUES (?)", (domain.strip().lower(),))
            conn.commit()
        except sqlite3.IntegrityError:
            pass
        conn.close()
        
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
