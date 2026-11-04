import os
import random
import requests
from datetime import datetime
import pytz
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = "galaxy_it_monitor_secret_key"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///galaxy_monitor.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'wallpapers')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db = SQLAlchemy(app)
IST = pytz.timezone('Asia/Kolkata')

GMAIL_USER = "Bhandaribharat216@gmail.com"

def get_ist_now():
    return datetime.now(IST).strftime("%Y-%m-%d %I:%M:%S %p")

# --- Database Models ---
class SystemDevice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(100), unique=True, nullable=False)
    hostname = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(100), nullable=False)
    local_ip = db.Column(db.String(50))
    tailscale_ip = db.Column(db.String(50))
    monitor_model = db.Column(db.String(150), default="Unknown Monitor")
    status = db.Column(db.String(20), default="Active")
    last_seen = db.Column(db.String(50))
    history_count = db.Column(db.Integer, default=0)
    last_history_sync = db.Column(db.String(50), default="N/A")
    screenshot_count = db.Column(db.Integer, default=0)
    last_screenshot_sync = db.Column(db.String(50), default="N/A")
    is_removed = db.Column(db.Boolean, default=False)

class SystemConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_password = db.Column(db.String(100), default="Bhandari")
    blocked_domains = db.Column(db.Text, default="facebook.com,instagram.com,twitter.com,youtube.com")
    wallpaper_url = db.Column(db.Text, default="")

def init_db():
    try:
        db.create_all()
        config = SystemConfig.query.first()
        if not config:
            config = SystemConfig(
                admin_password="Bhandari",
                blocked_domains="facebook.com,instagram.com,twitter.com,youtube.com",
                wallpaper_url=""
            )
            db.session.add(config)
            db.session.commit()
    except Exception as e:
        print(f"DB Init Exception: {e}")

with app.app_context():
    init_db()

# --- Static File Serving ---
@app.route('/static/wallpapers/<filename>')
def uploaded_wallpaper(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# --- Routes ---
@app.route('/')
def home():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.json or {}
        password = data.get('password')
        config = SystemConfig.query.first()
        admin_pass = config.admin_password if config and config.admin_password else "Bhandari"

        if password == admin_pass:
            session['logged_in'] = True
            return jsonify({'status': 'success', 'message': 'Login successful!'})
        return jsonify({'status': 'error', 'message': 'Invalid Password'}), 401

    if session.get('logged_in'):
        return redirect(url_for('dashboard'))
    
    try:
        return render_template('dashboard.html', page="login", phone_number=GMAIL_USER)
    except Exception as e:
        return f"Template Render Error on Login: {str(e)}", 500

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    try:
        config = SystemConfig.query.first()
        if not config:
            init_db()
            config = SystemConfig.query.first()

        devices = SystemDevice.query.filter_by(is_removed=False).all()
        
        raw_blocked = config.blocked_domains if (config and config.blocked_domains) else ""
        blocked_list = [d.strip() for d in raw_blocked.split(",") if d.strip()]
        
        return render_template(
            'dashboard.html', 
            page="dashboard", 
            devices=devices, 
            phone_number=GMAIL_USER,
            blocked_domains=blocked_list,
            wallpaper_url=config.wallpaper_url if config else ""
        )
    except Exception as e:
        return f"Dashboard Render Error: {str(e)}", 500

# --- Admin APIs for Domain Blocking & Wallpaper Upload ---
@app.route('/api/admin/add-blocked-domain', methods=['POST'])
def add_blocked_domain():
    if not session.get('logged_in'):
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    data = request.json or {}
    domain = data.get("domain", "").strip().lower()
    if not domain:
        return jsonify({'status': 'error', 'message': 'Domain empty'}), 400

    config = SystemConfig.query.first()
    if not config:
        init_db()
        config = SystemConfig.query.first()

    existing = [d.strip() for d in config.blocked_domains.split(",") if d.strip()] if config.blocked_domains else []
    if domain not in existing:
        existing.append(domain)
        config.blocked_domains = ",".join(existing)
        db.session.commit()

    return jsonify({'status': 'success', 'message': f'Domain {domain} blocked!'})

@app.route('/api/admin/remove-blocked-domain', methods=['POST'])
def remove_blocked_domain():
    if not session.get('logged_in'):
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    data = request.json or {}
    domain = data.get("domain", "").strip().lower()

    config = SystemConfig.query.first()
    if config and config.blocked_domains:
        existing = [d.strip() for d in config.blocked_domains.split(",") if d.strip()]
        if domain in existing:
            existing.remove(domain)
            config.blocked_domains = ",".join(existing)
            db.session.commit()

    return jsonify({'status': 'success', 'message': f'Domain {domain} unblocked!'})

@app.route('/api/admin/upload-wallpaper', methods=['POST'])
def upload_wallpaper():
    if not session.get('logged_in'):
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401

    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No selected file'}), 400

    if file:
        filename = secure_filename(f"wallpaper_{int(datetime.now().timestamp())}_{file.filename}")
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        full_url = f"{request.host_url.rstrip('/')}/static/wallpapers/{filename}"
        config = SystemConfig.query.first()
        if config:
            config.wallpaper_url = full_url
            db.session.commit()

        return jsonify({'status': 'success', 'wallpaper_url': full_url})

# --- Agent Heartbeat API ---
@app.route('/api/agent/heartbeat', methods=['POST'])
def agent_heartbeat():
    data = request.json or {}
    device_id = data.get("device_id")
    if not device_id:
        return jsonify({"error": "Device ID missing"}), 400

    device = SystemDevice.query.filter_by(device_id=device_id).first()
    if device and device.is_removed:
        return jsonify({"status": "removed"}), 403

    now_str = get_ist_now()
    if not device:
        device = SystemDevice(
            device_id=device_id,
            hostname=data.get("hostname", "Unknown"),
            username=data.get("username", "User"),
            local_ip=data.get("local_ip", request.remote_addr),
            tailscale_ip=data.get("tailscale_ip", "N/A"),
            monitor_model=data.get("monitor_model", "Unknown Monitor"),
            history_count=data.get("history_count", 0),
            last_history_sync=now_str if data.get("history_count") else "N/A",
            screenshot_count=data.get("screenshot_count", 0),
            last_screenshot_sync=now_str if data.get("screenshot_count") else "N/A"
        )
        db.session.add(device)
    else:
        if "monitor_model" in data:
            device.monitor_model = data.get("monitor_model", "Unknown Monitor")

    device.status = "Active"
    device.last_seen = now_str
    
    if "history_count" in data:
        device.history_count = data.get("history_count", 0)
        device.last_history_sync = now_str

    if "screenshot_count" in data:
        device.screenshot_count = data.get("screenshot_count", 0)
        device.last_screenshot_sync = now_str

    db.session.commit()

    config = SystemConfig.query.first()
    blocked_list = []
    wallpaper_target = ""

    if config:
        if config.blocked_domains:
            blocked_list = [d.strip() for d in config.blocked_domains.split(",") if d.strip()]
        wallpaper_target = config.wallpaper_url or ""

    return jsonify({
        "status": "success", 
        "server_time_ist": now_str,
        "blocked_domains": blocked_list,
        "wallpaper_url": wallpaper_target
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
