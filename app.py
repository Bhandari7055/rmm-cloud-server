from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3, os, random, smtplib
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta

app = Flask(__name__)
app.secret_key = "rmm_secret_key"

# Gmail SMTP Configuration
GMAIL_USER = "bhandaribharat216@gmail.com"
GMAIL_APP_PASS = "zkoz kalc iulk uwse"

otp_store = {}

def init_db():
    conn = sqlite3.connect("rmm.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS agents (hostname TEXT PRIMARY KEY, last_seen TEXT, screenshot_status TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS history (hostname TEXT, url TEXT, timestamp TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS policies (domain TEXT PRIMARY KEY)")
    cursor.execute("CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)")
    cursor.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('admin_password', 'admin123')")
    conn.commit()
    conn.close()

init_db()

def get_db():
    conn = sqlite3.connect("rmm.db")
    conn.row_factory = sqlite3.Row
    return conn

def send_otp_email(to_email, otp):
    msg = MIMEText(f"Your RMM Portal Password Reset OTP is: {otp}\nValid for 10 minutes.")
    msg['Subject'] = 'RMM Portal Password Reset OTP'
    msg['From'] = GMAIL_USER
    msg['To'] = to_email

    # Fast & reliable Port 587 with STARTTLS (Cloud Servers Fix)
    server = smtplib.SMTP('smtp.gmail.com', 587, timeout=15)
    server.starttls()
    clean_pass = GMAIL_APP_PASS.replace(" ", "")
    server.login(GMAIL_USER, clean_pass)
    server.sendmail(GMAIL_USER, [to_email], msg.as_string())
    server.quit()

def cleanup_old_history(conn):
    try:
        cutoff_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d %H:%M:%S")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM history WHERE timestamp < ?", (cutoff_date,))
        conn.commit()
    except Exception as e:
        print(f"[DB Cleanup Error] {e}")

@app.route("/")
def index():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM agents")
    agents = cursor.fetchall()
    cursor.execute("SELECT * FROM policies")
    policies = cursor.fetchall()
    conn.close()
    return render_template("dashboard.html", agents=agents, policies=policies)

@app.route("/agent/<hostname>")
def agent_history(hostname):
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    
    search_query = request.args.get("q", "").strip()
    conn = get_db()
    cursor = conn.cursor()
    
    if search_query:
        cursor.execute("SELECT rowid, * FROM history WHERE hostname = ? AND url LIKE ? ORDER BY timestamp DESC", (hostname, f"%{search_query}%"))
    else:
        cursor.execute("SELECT rowid, * FROM history WHERE hostname = ? ORDER BY timestamp DESC", (hostname,))
        
    history = cursor.fetchall()
    conn.close()
    return render_template("agent_history.html", hostname=hostname, history=history, search_query=search_query)

@app.route("/login", methods=["GET", "POST"])
def login():
    message = ""
    if request.method == "POST":
        password = request.form.get("password")
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM config WHERE key = 'admin_password'")
        row = cursor.fetchone()
        conn.close()
        
        current_pass = row['value'] if row else "admin123"
        if password == current_pass:
            session["logged_in"] = True
            return redirect(url_for("index"))
        else:
            message = "Invalid Password!"
            
    return f'''
        <div style="margin: 50px auto; width: 320px; text-align: center; font-family: Arial;">
            <h2>RMM Cloud Login</h2>
            <p style="color:red;">{message}</p>
            <form method="post">
                <input type="password" name="password" placeholder="Password" required style="padding: 10px; width: 100%; box-sizing: border-box;"><br><br>
                <button type="submit" style="padding: 10px 20px; width: 100%; background: #007bff; color: white; border: none; cursor: pointer;">Login</button>
            </form>
            <br>
            <a href="/forgot-password" style="color: #007bff; text-decoration: none;">Forgot Password? Reset via OTP</a>
        </div>
    '''

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    msg = ""
    if request.method == "POST":
        action = request.form.get("action")
        if action == "send_otp":
            otp = str(random.randint(100000, 999999))
            otp_store["admin_otp"] = otp
            try:
                send_otp_email(GMAIL_USER, otp)
                msg = f"OTP Sent Successfully to {GMAIL_USER}!"
                return render_template("reset_password.html", step=2, msg=msg)
            except Exception as e:
                msg = f"Failed to send OTP: {e}"
        elif action == "verify_reset":
            entered_otp = request.form.get("otp")
            new_pass = request.form.get("new_password")
            if entered_otp == otp_store.get("admin_otp"):
                conn = get_db()
                cursor
