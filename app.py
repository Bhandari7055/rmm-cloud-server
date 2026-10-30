from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import json
import os
import random
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
import pytz

app = Flask(__name__)
app.secret_key = "rmm_super_secret_key"

DATA_FILE = "rmm_data.json"
IST = pytz.timezone('Asia/Kolkata')

def get_ist_time():
    return datetime.now(IST).strftime("%Y-%m-%d %I:%M:%S %p")

def get_today_str():
    return datetime.now(IST).strftime("%Y-%m-%d")

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
        "history": {},
        "activity_logs": {}
    }

def save_data(data):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving data: {e}")

def calculate_24h_stats(hostname, data):
    logs = data.get("activity_logs", {}).get(hostname, [])
    now = datetime.now(IST)
    cutoff = now - timedelta(hours=24)
    
    active_count = 0
    idle_count = 0
    
    for entry in logs:
        try:
            t = datetime.strptime(entry["timestamp"], "%Y-%m-%d %I:%M:%S %p")
            t = IST.localize(t)
            if t >= cutoff:
                if entry.get("status") == "Active":
                    active_count += 1
                else:
                    idle_count += 1
        except Exception:
            pass
            
    # Each ping is recorded every 30 seconds (0.5 mins)
    active_hours = round((active_count * 0.5) / 60, 1)
    idle_hours = round((idle_count * 0.5) / 60, 1)
    return active_hours, idle_hours

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
    
    for host, sys_info in systems.items():
        try:
            last_time = datetime.strptime(sys_info["last_active"], "%Y-%m-%d %I:%M:%S %p")
            last_time = IST.localize(last_time)
            user_idle = sys_info.get("user_idle", False)
            
            # Mark Offline/Idle if last ping > 90 sec or user idle > 2 mins
            if (now_ist - last_time).total_seconds() > 90 or user_idle:
                sys_info["agent_status"] = "Offline / Idle"
            else:
                sys_info["agent_status"] = "Active"
                
            active_h, idle_h = calculate_24h_stats(host, data)
            sys_info["work_hours_24h"] = f"{active_h} hrs Active / {idle_h} hrs Idle"
        except Exception:
            sys_info["agent_status"] = "Offline / Idle"
            sys_info["work_hours_24h"] = "0.0 hrs Active / 0.0 hrs Idle"

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
    
    # Fast2SMS API Key (Aap apni Fast2SMS API Key yahan daal sakte ho)
    api_key = "YOUR_FAST2SMS_API_KEY"
    
    try:
        url = "https://www.fast2sms.com/dev/bulkV2"
        payload = urllib.parse.urlencode({
            'variables_values': otp,
            'route': 'otp',
            'numbers': phone
        }).encode('utf-8')
        
        req = urllib.request.Request(url, data=payload, headers={
            'authorization': api_key,
            'Content-Type': 'application/x-www-form-urlencoded'
        })
        
        with urllib.request.urlopen(req, timeout=5) as response:
            pass
    except Exception as e:
        print(f"SMS Dispatch Triggered: {e}")
        
    return jsonify({
        "status": "success", 
        "message": f"OTP sent via SMS to +91-XXXXXX{phone[-4:]}!"
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
    if action == "block" and domain:
        if domain not in domains:
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
    user_idle = req_data.get("user_idle", False)
    screenshot_status = req_data.get("screenshot_status", "Active Stream")
    
    if not hostname:
        return jsonify({"error": "Hostname required"}), 400
        
    data = load_data()
    now_ist = get_ist_time()
    
    status_str = "Offline / Idle" if user_idle else "Active"
    
    data["systems"][hostname] = {
        "hostname": hostname,
        "agent_status": status_str,
        "user_idle": user_idle,
        "screenshot_status": "Paused (Idle)" if user_idle else screenshot_status,
        "last_active": now_ist
    }
    
    if "activity_logs" not in data:
        data["activity_logs"] = {}
    if hostname not in data["activity_logs"]:
        data["activity_logs"][hostname] = []
        
    data["activity_logs"][hostname].append({"timestamp": now_ist, "status": "Active" if not user_idle else "Idle"})
    data["activity_logs"][hostname] = data["activity_logs"][hostname][-2880:]
    
    save_data(data)
    return jsonify({"status": "acknowledged", "blocked_domains": data.get("blocked_domains", [])})

@app.route("/api/system/history", methods=["GET", "POST"])
def system_history():
    data = load_data()
    if request.method == "POST":
        req = request.json or {}
        hostname = req.get("hostname")
        url = req.get("url")
        timestamp = req.get("timestamp", get_ist_time())
        date_str = req.get("date", get_today_str())
        
        if hostname and url:
            if "history" not in data:
                data["history"] = {}
            if hostname not in data["history"]:
                data["history"][hostname] = {}
            if date_str not in data["history"][hostname]:
                data["history"][hostname][date_str] = []
            
            data["history"][hostname][date_str].append({"url": url, "timestamp": timestamp})
            save_data(data)
        return jsonify({"status": "logged"})
        
    elif request.method == "GET":
        hostname = request.args.get("hostname")
        selected_date = request.args.get("date", get_today_str())
        if hostname:
            host_hist = data.get("history", {}).get(hostname, {})
            return jsonify({"hostname": hostname, "date": selected_date, "history": host_hist.get(selected_date, [])})
        return jsonify({"history": data.get("history", {})})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
