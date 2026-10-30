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
        "activity_logs": {},
        "target_wallpaper": ""
    }

def save_data(data):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving data: {e}")

def cleanup_old_history(data):
    now = datetime.now(IST)
    cutoff = now - timedelta(days=90)
    
    history = data.get("history", {})
    for host in list(history.keys()):
        for date_str in list(history[host].keys()):
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                dt = IST.localize(dt)
                if dt < cutoff:
                    del history[host][date_str]
            except Exception:
                pass

def calculate_shift_stats(system_key, data):
    logs = data.get("activity_logs", {}).get(system_key, [])
    now = datetime.now(IST)
    
    if now.hour >= 6:
        shift_start = now.replace(hour=6, minute=0, second=0, microsecond=0)
    else:
        shift_start = (now - timedelta(days=1)).replace(hour=6, minute=0, second=0, microsecond=0)
        
    active_count = 0
    idle_count = 0
    
    for entry in logs:
        try:
            t = datetime.strptime(entry["timestamp"], "%Y-%m-%d %I:%M:%S %p")
            t = IST.localize(t)
            if t >= shift_start:
                if entry.get("status") == "Active":
                    active_count += 1
                else:
                    idle_count += 1
        except Exception:
            pass
            
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
    cleanup_old_history(data)
    save_data(data)
    
    systems = data.get("systems", {})
    now_ist = datetime.now(IST)
    
    for sys_key, sys_info in systems.items():
        try:
            last_time = datetime.strptime(sys_info["last_active"], "%Y-%m-%d %I:%M:%S %p")
            last_time = IST.localize(last_time)
            user_idle = sys_info.get("user_idle", False)
            diff_seconds = (now_ist - last_time).total_seconds()
            
            if diff_seconds >= 172800:
                sys_info["agent_status"] = "2 Day Not Active System"
            elif diff_seconds > 90 or user_idle:
                sys_info["agent_status"] = "Offline / Idle"
            else:
                sys_info["agent_status"] = "Active"
                
            active_h, idle_h = calculate_shift_stats(sys_key, data)
            sys_info["work_hours_24h"] = f"{active_h} hrs Active / {idle_h} hrs Idle"
        except Exception:
            sys_info["agent_status"] = "2 Day Not Active System"
            sys_info["work_hours_24h"] = "0.0 hrs Active / 0.0 hrs Idle"

    return render_template("dashboard.html", 
                           blocked_domains=data.get("blocked_domains", []), 
                           systems=systems,
                           target_wallpaper=data.get("target_wallpaper", ""),
                           phone_number=data.get("phone_number", "7055361662"))

@app.route("/api/set-wallpaper", methods=["POST"])
def set_wallpaper():
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
    req = request.json or {}
    wallpaper_url = req.get("wallpaper_url", "").strip()
    data = load_data()
    data["target_wallpaper"] = wallpaper_url
    save_data(data)
    return jsonify({"status": "success", "wallpaper_url": wallpaper_url})

@app.route("/api/system/delete", methods=["POST"])
def delete_system():
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
    req = request.json or {}
    sys_key = req.get("system_key")
    if sys_key:
        data = load_data()
        if sys_key in data.get("systems", {}):
            del data["systems"][sys_key]
        if sys_key in data.get("activity_logs", {}):
            del data["activity_logs"][sys_key]
        if sys_key in data.get("history", {}):
            del data["history"][sys_key]
        save_data(data)
        return jsonify({"status": "success", "message": f"{sys_key} removed"})
    return jsonify({"error": "Invalid request"}), 400

@app.route("/send-otp", methods=["POST"])
def send_otp():
    data = load_data()
    otp = str(random.randint(100000, 999999))
    session["reset_otp"] = otp
    phone = data.get("phone_number", "7055361662")
    
    api_key = "YOUR_FAST2SMS_API_KEY"  # Replace with actual Fast2SMS Key
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
        "message": f"OTP successfully sent via SMS to +91-XXXXXX{phone[-4:]}!"
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
    hostname = req_data.get("hostname", "Unknown")
    username = req_data.get("username", "User")
    ip_address = req_data.get("ip_address", request.remote_addr)
    user_idle = req_data.get("user_idle", False)
    
    if not hostname:
        return jsonify({"error": "Hostname required"}), 400
        
    data = load_data()
    now_ist = get_ist_time()
    
    # Key created per user: "DESKTOP-ABC \ bharat"
    system_key = f"{hostname} \\ {username}"
    status_str = "Offline / Idle" if user_idle else "Active"
    
    data["systems"][system_key] = {
        "hostname": hostname,
        "username": username,
        "ip_address": ip_address,
        "agent_status": status_str,
        "user_idle": user_idle,
        "screenshot_status": "Idle / Error" if user_idle else "Active Stream",
        "last_active": now_ist
    }
    
    if "activity_logs" not in data:
        data["activity_logs"] = {}
    if system_key not in data["activity_logs"]:
        data["activity_logs"][system_key] = []
        
    data["activity_logs"][system_key].append({"timestamp": now_ist, "status": "Active" if not user_idle else "Idle"})
    data["activity_logs"][system_key] = data["activity_logs"][system_key][-5760:]
    
    save_data(data)
    return jsonify({
        "status": "acknowledged", 
        "blocked_domains": data.get("blocked_domains", []),
        "target_wallpaper": data.get("target_wallpaper", "")
    })

@app.route("/api/system/history", methods=["GET", "POST"])
def system_history():
    data = load_data()
    if request.method == "POST":
        req = request.json or {}
        hostname = req.get("hostname")
        username = req.get("username", "User")
        url = req.get("url")
        timestamp = req.get("timestamp", get_ist_time())
        date_str = req.get("date", get_today_str())
        
        system_key = f"{hostname} \\ {username}"
        
        if system_key and url:
            if "history" not in data:
                data["history"] = {}
            if system_key not in data["history"]:
                data["history"][system_key] = {}
            if date_str not in data["history"][system_key]:
                data["history"][system_key][date_str] = []
            
            data["history"][system_key][date_str].append({"url": url, "timestamp": timestamp})
            save_data(data)
        return jsonify({"status": "logged"})
        
    elif request.method == "GET":
        system_key = request.args.get("hostname")
        selected_date = request.args.get("date", get_today_str())
        if system_key:
            host_hist = data.get("history", {}).get(system_key, {})
            return jsonify({"hostname": system_key, "date": selected_date, "history": host_hist.get(selected_date, [])})
        return jsonify({"history": data.get("history", {})})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
