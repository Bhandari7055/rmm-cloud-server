from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pytz
import os

app = Flask(__name__)
app.secret_key = "galaxy_it_monitor_secret_key"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///galaxy_monitor.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
IST = pytz.timezone('Asia/Kolkata')

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
    status = db.Column(db.String(20), default="Active")
    last_seen = db.Column(db.String(50))
    is_removed = db.Column(db.Boolean, default=False)

class SystemConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_phone = db.Column(db.String(20), default="XXXXXXXX62")

with app.app_context():
    try:
        db.create_all()
        if not SystemConfig.query.first():
            db.session.add(SystemConfig(admin_phone="XXXXXXXX62"))
            db.session.commit()
    except Exception as e:
        print(f"DB Init Exception: {e}")

# --- Routes ---
@app.route('/')
def home():
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    try:
        devices = SystemDevice.query.filter_by(is_removed=False).all()
        config = SystemConfig.query.first()
        phone_no = config.admin_phone if config else "1662"
        
        # Template ko expected variables pass kiye ja rahe hain
        return render_template('dashboard.html', devices=devices, phone_number=phone_no)
    except Exception as e:
        return f"Dashboard Error: {str(e)}", 500

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
            tailscale_ip=data.get("tailscale_ip", "N/A")
        )
        db.session.add(device)

    device.status = "Active"
    device.last_seen = now_str
    db.session.commit()
    return jsonify({"status": "success", "server_time_ist": now_str})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
