from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import json
import os
import random
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "rmm_super_secret_key"

DATA_FILE = "rmm_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {
        "blocked_domains": [],
        "systems": {},
        "admin_password": "admin",
        "phone_number": "9876543210",
        "history": {}
    }

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

@app.route("/")
def home():
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    data = load_data()
    if request.method == "POST":
        password = request.form.get("password")
        if password == data.get("admin_password"):
            session["logged_in"] = True
            return redirect(url_for("dashboard"))
        return render_template("login.html", error="Incorrect Password")
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    data = load_data()
    return render_template("dashboard.html", 
                           blocked_domains=data.get("blocked_domains", []), 
                           systems=data.get("systems", {}))

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    data = load_data()
    if request.method == "POST":
        otp = str(random.randint(100000, 999999))
        session["reset_otp"] = otp
        print(f"[OTP DEBUG] Sent OTP {otp} to mobile number {data.get('phone_number')}")
        return render_template("verify_otp.html", message=f"OTP sent to {data.get('phone_number')}")
    return render_template("forgot_password.html")

@app.route("/verify-otp", methods=["POST"])
def verify_otp():
    user_otp = request.form.get("otp")
    new_pass = request.form.get("new_password")
    if user_otp == session.get("reset_otp"):
        data = load_data()
        data["admin_password"] = new_pass
        save_data(data)
        session.pop("reset_otp", None)
        return render_template("login.html", success="Password changed successfully!")
    return render_template("verify_otp.html", error="Invalid OTP")

# --- API ENDPOINTS FOR AGENT & DASHBOARD ---

@app.route("/api/blocked-domains", methods=["GET", "POST"])
def manage_blocked_domains():
    data = load_data()
    if request.method == "GET":
        return jsonify({"blocked_domains": data.get("blocked_domains", [])})
    
    req_data = request.json or {}
    domain = req_data.get("domain", "").strip().lower()
    action = req_data.get("action", "block")
    
    domains = data.get("blocked_domains", [])
    if action == "block" and domain and domain not in domains:
        domains.append(domain)
    elif action == "unblock" and domain in domains:
        domains.remove(domain)
        
    data["blocked_domains"] = domains
    save_data(data)
    return jsonify({"status": "success", "blocked_domains": domains})

@app.route("/api/system/ping", methods=["POST"])
def system_ping():
    req_data = request.json or {}
    hostname = req_data.get("hostname")
    screenshot_status = req_data.get("screenshot_status", "Paused (User Idle)")
    
    if not hostname:
        return jsonify({"error": "Hostname required"}), 400
        
    data = load_data()
    now_str = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    
    data["systems"][hostname] = {
        "hostname": hostname,
        "agent_status": "Active",
        "screenshot_status": screenshot_status,
        "last_active": now_str
    }
    save_data(data)
    return jsonify({"status": "acknowledged"})

@app.route("/api/system/history", methods=["GET", "POST", "DELETE"])
def system_history():
    data = load_data()
    
    if request.method == "POST":
        req = request.json or {}
        hostname = req.get("hostname")
        url = req.get("url")
        timestamp = req.get("timestamp", datetime.now().strftime("%Y-%m-%d %I:%M:%S %p"))
        
        if hostname and url:
            if hostname not in data["history"]:
                data["history"][hostname] = []
            data["history"][hostname].append({"url": url, "timestamp": timestamp})
            save_data(data)
        return jsonify({"status": "logged"})
        
    elif request.method == "GET":
        hostname = request.args.get("hostname")
        if hostname:
            history_list = data["history"].get(hostname, [])
            # 3-Month filter check
            cutoff = datetime.now() - timedelta(days=90)
            valid_history = []
            for item in history_list:
                try:
                    dt = datetime.strptime(item["timestamp"], "%Y-%m-%d %I:%M:%S %p")
                    if dt >= cutoff:
                        valid_history.append(item)
                except Exception:
                    valid_history.append(item)
            return jsonify({"hostname": hostname, "history": valid_history})
        return jsonify({"history": data.get("history", {})})
        
    elif request.method == "DELETE":
        req = request.json or {}
        hostname = req.get("hostname")
        url_to_delete = req.get("url")
        
        if hostname in data["history"]:
            data["history"][hostname] = [item for item in data["history"][hostname] if item["url"] != url_to_delete]
            save_data(data)
            return jsonify({"status": "deleted"})
        return jsonify({"error": "Host not found"}), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
