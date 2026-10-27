from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3, os
from datetime import datetime, timezone

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

@app.route("/")
def index():
    if "logged_in" in session:
        return redirect(url_for("dashboard"))
    return """<form action="/login" method="POST" style="margin:100px auto; width:300px; text-align:center;">
    <h2>RMM Admin Login</h2>
    <input type="password" name="password" placeholder="Enter Admin Password" required style="padding:10px; width:100%; margin-bottom:10px;"><br>
    <button type="submit" style="padding:10px 20px; background:#007bff; color:white; border:none; cursor:pointer;">Login</button>
    </form>"""

@app.route("/login", methods=["POST"])
def login():
    if request.form.get("password") == "admin123":
        session["logged_in"] = True
        return redirect(url_for("dashboard"))
    return 'Invalid Password! <a href="/">Try again</a>'

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("index"))

@app.route("/dashboard")
def dashboard():
    if "logged_in" not in session:
        return redirect(url_for("index"))
    conn = sqlite3.connect("rmm.db")
    cursor = conn.cursor()
    cursor.execute("SELECT hostname, last_seen FROM agents")
    agents = [{"hostname": row[0], "last_seen": row[1]} for row in cursor.fetchall()]
    cursor.execute("SELECT hostname, url, timestamp FROM history ORDER BY timestamp DESC")
    history = cursor.fetchall()
    cursor.execute("SELECT domain FROM policies")
    policies = [row[0] for row in cursor.fetchall()]
    conn.close()
    return render_template("dashboard.html", agents=agents, history=history, policies=policies)

@app.route("/api/policy/add", methods=["POST"])
def add_policy():
    data = request.json or {}
    domain = data.get("domain", "").strip().lower()
    if domain:
        conn = sqlite3.connect("rmm.db")
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO policies (domain) VALUES (?)", (domain,))
        conn.commit()
        conn.close()
    return jsonify({"status": "ok"})

@app.route("/api/policy/delete", methods=["POST"])
def delete_policy():
    data = request.json or {}
    domain = data.get("domain", "").strip().lower()
    if domain:
        conn = sqlite3.connect("rmm.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM policies WHERE domain = ?", (domain,))
        conn.commit()
        conn.close()
    return jsonify({"status": "ok"})

@app.route("/api/system/ping", methods=["POST"])
def ping():
    data = request.json or {}
    hostname = data.get("hostname", "Unknown")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect("rmm.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO agents (hostname, last_seen) VALUES (?, ?)", (hostname, now))
    cursor.execute("SELECT domain FROM policies")
    policies = [row[0] for row in cursor.fetchall()]
    conn.commit()
    conn.close()
    return jsonify({"status": "ok", "policies": policies})

@app.route("/api/system/history", methods=["POST"])
def save_history():
    data = request.json or {}
    hostname, url = data.get("hostname"), data.get("url")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    if hostname and url:
        conn = sqlite3.connect("rmm.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO history (hostname, url, timestamp) VALUES (?, ?, ?)", (hostname, url, now))
        conn.commit()
        conn.close()
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)