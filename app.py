from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3, os
from datetime import datetime, timezone, timedelta

app = Flask(__name__)
app.secret_key = "rmm_secret_key"

def init_db():
    conn = sqlite3.connect("rmm.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS agents (hostname TEXT PRIMARY KEY, last_seen TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS history (hostname TEXT, url TEXT, timestamp TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS policies (domain TEXT PRIMARY KEY)")
    conn.commit()
    conn.close()

init_db()

def get_db():
    conn = sqlite3.connect("rmm.db")
    conn.row_factory = sqlite3.Row
    return conn

def cleanup_old_history(conn):
    try:
        # 90 days (3 months) se purani history auto delete
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
    
    cursor.execute("SELECT * FROM history ORDER BY timestamp DESC LIMIT 100")
    history = cursor.fetchall()
    
    cursor.execute("SELECT * FROM policies")
    policies = cursor.fetchall()
    
    conn.close()
    return render_template("dashboard.html", agents=agents, history=history, policies=policies)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == "admin123":
            session["logged_in"] = True
            return redirect(url_for("index"))
    return '''
        <form method="post" style="margin: 50px auto; width: 300px; text-align: center;">
            <h2>RMM Cloud Login</h2>
            <input type="password" name="password" placeholder="Password" required style="padding: 10px; width: 100%;"><br><br>
            <button type="submit" style="padding: 10px 20px;">Login</button>
        </form>
    '''

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("login"))

@app.route("/api/system/ping", methods=["POST"])
def ping():
    data = request.json or {}
    hostname = data.get("hostname", "Unknown")
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO agents (hostname, last_seen) VALUES (?, ?)", (hostname, now_str))
    
    cursor.execute("SELECT domain FROM policies")
    policies = [row["domain"] for row in cursor.fetchall()]
    
    conn.commit()
    conn.close()
    return jsonify({"status": "ok", "policies": policies})

@app.route("/api/system/history", methods=["POST"])
def history_log():
    data = request.json or {}
    hostname = data.get("hostname", "Unknown")
    url = data.get("url", "")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if url:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO history (hostname, url, timestamp) VALUES (?, ?, ?)", (hostname, url, now_str))
        conn.commit()
        
        # 3 months cleanup run karein
        cleanup_old_history(conn)
        conn.close()
        
    return jsonify({"status": "ok"})

@app.route("/api/policy/add", methods=["POST"])
def add_policy():
    domain = request.form.get("domain", "").strip()
    if domain:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO policies (domain) VALUES (?)", (domain,))
        conn.commit()
        conn.close()
    return redirect(url_for("index"))

@app.route("/api/policy/delete", methods=["POST"])
def delete_policy():
    domain = request.form.get("domain", "").strip()
    if domain:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM policies WHERE domain = ?", (domain,))
        conn.commit()
        conn.close()
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
