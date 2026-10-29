from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import json
import os
import random
from datetime import datetime, timedelta
import pytz

app = Flask(__name__)
app.secret_key = "rmm_super_secret_key"

DATA_FILE = "rmm_data.json"
IST = pytz.timezone('Asia/Kolkata')

def get_ist_time():
    return datetime.now(IST).strftime("%Y-%m-%d %I:%M:%S %p")

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
                data["phone_number"] = "7055361662"
                return data
        except Exception:
            pass
    return {
        "blocked_domains": [],
        "systems": {},
        "admin_password": "admin",
        "phone_number": "7055361662",
        "history": {}
    }

def save_data(data):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving data: {e}")

def clean_old_history(data):
    cutoff_date = datetime.now(IST) - timedelta(days=90)
    for host in data.get("history", {}):
        filtered = []
        for item in data["history"][host]:
            try:
                item_time = datetime.strptime(item["timestamp"], "%Y-%m-%d %I:%M:%S %p")
                item_time = IST.localize(item_time)
                if item_time >= cutoff_date:
                    filtered.append(item)
            except Exception:
                filtered.append(item)
        data["history"][host] = filtered
    return data

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

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("login"))

@app.route("/dashboard")
def dashboard():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    data = load_data()
    
    systems = data.get("systems", {})
    now_ist = datetime.now(IST)
    
    # Dynamic Agent Offline / Idle Status Check (2 mins inactivity)
    for host, sys_info in systems.items():
        try:
            last_time = datetime.strptime(sys_info["last_active"], "%Y-%m-%d %I:%M:%S %p")
            last_time = IST.localize(last_time)
            if (now_ist - last_time).total_seconds() > 120:
                sys_info["agent_status"] = "Offline / Idle"
            else:
                sys_info["agent_status"] = "Active"
        except Exception:
            pass

    return render_template("dashboard.html", 
                           blocked_domains=data.get("blocked_domains", []), 
                           systems=systems,
                           phone_number=data.get("phone_number", "7055361662"))

@app.route("/send-otp", methods=["POST"])
def send_otp():
    data = load_data()
    otp = str(random.randint(100000, 999999))
    session["reset_otp"] = otp
    phone = data.get("phone_number", "7055361662")
    return jsonify({
        "status": "success", 
        "message": f"OTP sent to +91-XXXXXX{phone[-4:]}! (OTP: {otp})",
        "otp": otp
    })

@app.route("/reset-password", methods=["POST"])
def reset_password():
    req = request.json or {}
    user_otp = req.get("otp")
    new_pass = req.get("new_password")
    
    if user_otp and user_otp == session.get("reset_otp"):
        data = load_data()
        data["admin_password"] = new_pass
        save_data(data)
        session.pop("reset_otp", None)
        return jsonify({"status": "success", "message": "Password changed successfully!"})
    return jsonify({"status": "error", "message": "Invalid OTP entered!"}), 400

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
    now_ist = get_ist_time()
    
    data["systems"][hostname] = {
        "hostname": hostname,
        "agent_status": "Active",
        "screenshot_status": screenshot_status,
        "last_active": now_ist
    }
    save_data(data)
    return jsonify({"status": "acknowledged"})

@app.route("/api/system/history", methods=["GET", "POST", "DELETE"])
def system_history():
    data = load_data()
    data = clean_old_history(data)
    
    if request.method == "POST":
        req = request.json or {}
        hostname = req.get("hostname")
        url = req.get("url")
        timestamp = req.get("timestamp", get_ist_time())
        
        if hostname and url:
            if "history" not in data:
                data["history"] = {}
            if hostname not in data["history"]:
                data["history"][hostname] = []
            
            if not data["history"][hostname] or data["history"][hostname][-1].get("url") != url:
                data["history"][hostname].append({"url": url, "timestamp": timestamp})
                save_data(data)
        return jsonify({"status": "logged"})
        
    elif request.method == "GET":
        hostname = request.args.get("hostname")
        if hostname:
            return jsonify({"hostname": hostname, "history": data.get("history", {}).get(hostname, [])})
        return jsonify({"history": data.get("history", {})})
        
    elif request.method == "DELETE":
        req = request.json or {}
        hostname = req.get("hostname")
        url_to_delete = req.get("url")
        
        if hostname in data.get("history", {}):
            data["history"][hostname] = [item for item in data["history"][hostname] if item.get("url") != url_to_delete]
            save_data(data)
            return jsonify({"status": "deleted"})
        return jsonify({"error": "Host not found"}), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
