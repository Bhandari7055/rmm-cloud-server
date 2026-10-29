import os
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template, render_template_string, redirect, url_for, session
from twilio.rest import Client

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "rmm_secret_key_12345")

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

init_db()

@app.route('/')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
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

# --- DOMAIN BLOCK & UNBLOCK API FOR AGENT ---
@app.route('/api/blocked-domains', methods=['GET'])
def get_blocked_domains():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT domain FROM blocked_domains")
    rows = cursor.fetchall()
    conn.close()
    domains = [row['domain'] for row in rows]
    return jsonify({"blocked_domains": domains})

@app.route('/block-domain', methods=['POST'])
def block_domain():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    domain = request.form.get('domain')
    if domain:
        clean_domain = domain.strip().lower().replace('https://', '').replace('http://', '').replace('www.', '')
        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO blocked_domains (domain) VALUES (?)", (clean_domain,))
            conn.commit()
        except sqlite3.IntegrityError:
            pass
        conn.close()
    return redirect(url_for('dashboard'))

@app.route('/unblock-domain/<int:domain_id>', methods=['POST'])
def unblock_domain(domain_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM blocked_domains WHERE id=?", (domain_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/api/system/ping', methods=['POST'])
def system_ping():
    data = request.json or {}
    hostname = data.get('hostname')
    screenshot_status = data.get('screenshot_status', 'Active')
    if not hostname:
        return jsonify({"status": "error"}), 400
        
    now = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    clean_status = "Active" if "Active" in str(screenshot_status) else "Paused (User Idle)"
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO agents (hostname, screenshot_status, last_seen)
        VALUES (?, ?, ?)
        ON CONFLICT(hostname) DO UPDATE SET
            screenshot_status = ?,
            last_seen = ?
    ''', (hostname, clean_status, now, clean_status, now))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@app.route('/api/system/history', methods=['POST'])
def log_history():
    data = request.json or {}
    hostname = data.get('hostname')
    url = data.get('url')
    timestamp = data.get('timestamp') or datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    if hostname and url:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO history (hostname, url, timestamp) VALUES (?, ?, ?)", (hostname, url, timestamp))
        conn.commit()
        conn.close()
    return jsonify({"status": "success"})

@app.route('/agent/<hostname>')
def view_agent_history(hostname):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM history WHERE hostname=? ORDER BY id DESC", (hostname,))
    history_records = cursor.fetchall()
    conn.close()
    return render_template('agent_history.html', hostname=hostname, history=history_records)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
