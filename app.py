import os
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template, redirect, url_for, session

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "rmm_secret_key_12345")

DB_FILE = "rmm.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Auth table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    ''')
    
    # Admin default user
    cursor.execute("INSERT OR IGNORE INTO users (username, password) VALUES ('admin', 'admin123')")
    
    # Systems status table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS systems (
            hostname TEXT PRIMARY KEY,
            last_ping TIMESTAMP,
            screenshot_status TEXT
        )
    ''')
    
    # Blocked domains table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS blocked_domains (
            domain TEXT PRIMARY KEY
        )
    ''')
    
    # Window history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS window_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hostname TEXT,
            url TEXT,
            timestamp TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# --- Auth Routes ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            session['user'] = username
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', msg="Invalid Credentials!")
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

# Both /reset-password and /forgot-password routes enabled to fix 404
@app.route('/reset-password', methods=['GET', 'POST'])
@app.route('/forgot-password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        username = request.form.get('username')
        new_password = request.form.get('new_password')
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET password=? WHERE username=?", (new_password, username))
        conn.commit()
        conn.close()
        
        return render_template('reset_password.html', msg="Password Updated Successfully! Go back to login.")
        
    return render_template('reset_password.html')

# --- Dashboard ---
@app.route('/')
@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Fetch Systems
    cursor.execute("SELECT hostname, last_ping, screenshot_status FROM systems")
    raw_systems = cursor.fetchall()
    
    systems = []
    now = datetime.now()
    for sys in raw_systems:
        hostname, last_ping_str, screenshot_status = sys
        is_active = False
        if last_ping_str:
            try:
                last_ping = datetime.strptime(last_ping_str, "%Y-%m-%d %H:%M:%S")
                if now - last_ping < timedelta(seconds=30):
                    is_active = True
            except Exception:
                pass
                
        systems.append({
            "hostname": hostname,
            "last_ping": last_ping_str,
            "is_active": is_active,
            "screenshot_status": screenshot_status
        })
        
    # Fetch Blocked Domains
    cursor.execute("SELECT domain FROM blocked_domains")
    blocked_domains = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    return render_template('dashboard.html', systems=systems, blocked_domains=blocked_domains)

# --- Agent APIs ---
@app.route('/api/system/ping', methods=['POST'])
def api_ping():
    data = request.json or {}
    hostname = data.get('hostname')
    screenshot_status = data.get('screenshot_status', 'Active')
    
    if hostname:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO systems (hostname, last_ping, screenshot_status)
            VALUES (?, ?, ?)
            ON CONFLICT(hostname) DO UPDATE SET
                last_ping=excluded.last_ping,
                screenshot_status=excluded.screenshot_status
        ''', (hostname, now_str, screenshot_status))
        conn.commit()
        conn.close()
        return jsonify({"status": "success"})
    return jsonify({"error": "hostname required"}), 400

@app.route('/api/blocked-domains', methods=['GET', 'POST', 'DELETE'])
def api_blocked_domains():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    if request.method == 'GET':
        cursor.execute("SELECT domain FROM blocked_domains")
        domains = [row[0] for row in cursor.fetchall()]
        conn.close()
        return jsonify({"blocked_domains": domains})
        
    elif request.method == 'POST':
        data = request.json or {}
        domain = data.get('domain', '').strip().lower()
        if domain:
            cursor.execute("INSERT OR IGNORE INTO blocked_domains (domain) VALUES (?)", (domain,))
            conn.commit()
        conn.close()
        return jsonify({"status": "success"})
        
    elif request.method == 'DELETE':
        data = request.json or {}
        domain = data.get('domain', '').strip().lower()
        if domain:
            cursor.execute("DELETE FROM blocked_domains WHERE domain=?", (domain,))
            conn.commit()
        conn.close()
        return jsonify({"status": "success"})

@app.route('/api/system/history', methods=['POST'])
def api_history():
    data = request.json or {}
    hostname = data.get('hostname')
    url = data.get('url')
    timestamp = data.get('timestamp')
    
    if hostname and url:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO window_history (hostname, url, timestamp) VALUES (?, ?, ?)", 
                       (hostname, url, timestamp))
        conn.commit()
        conn.close()
        return jsonify({"status": "success"})
    return jsonify({"error": "invalid payload"}), 400

@app.route('/history/<hostname>')
def view_history(hostname):
    if 'user' not in session:
        return redirect(url_for('login'))
        
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT url, timestamp FROM window_history WHERE hostname=? ORDER BY id DESC LIMIT 100", (hostname,))
    records = cursor.fetchall()
    conn.close()
    
    return render_template('agent_history.html', hostname=hostname, records=records)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
