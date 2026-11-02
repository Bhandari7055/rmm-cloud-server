from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pytz
import random
import smtplib
from email.mime.text import MIMEText

app = Flask(__name__)
app.secret_key = "galaxy_it_monitor_secret_key"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///galaxy_monitor.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
IST = pytz.timezone('Asia/Kolkata')

def get_ist_now():
    return datetime.now(IST)

# --- Database Models ---
class SystemDevice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(100), unique=True, nullable=False)
    hostname = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(100), nullable=False)
    local_ip = db.Column(db.String(50))
    tailscale_ip = db.Column(db.String(50))
    status = db.Column(db.String(20), default="Offline")
    last_seen = db.Column(db.String(50))
    is_removed = db.Column(db.Boolean, default=False)

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.String(50))
    action_type = db.Column(db.String(50))
    details = db.Column(db.Text)

class AdminConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    password = db.Column(db.String(100), default="Bhandari")

with app.app_context():
    db.create_all()
    if not AdminConfig.query.first():
        db.session.add(AdminConfig(password="Bhandari"))
        db.session.commit()

# --- Heartbeat API (30 Seconds Check) ---
@app.route('/api/agent/heartbeat', methods=['POST'])
def agent_heartbeat():
    data = request.json or {}
    device_id = data.get("device_id")
    
    if not device_id:
        return jsonify({"error": "Device ID required"}), 400
        
    device = SystemDevice.query.filter_by(device_id=device_id).first()
    if device and device.is_removed:
        return jsonify({"status": "blocked", "message": "Device is removed from monitoring"}), 403

    now_str = get_ist_now().strftime("%Y-%m-%d %I:%M:%S %p")
    
    if not device:
        device = SystemDevice(
            device_id=device_id,
            hostname=data.get("hostname", "Unknown"),
            username=data.get("username", "User"),
            local_ip=data.get("local_ip", "N/A"),
            tailscale_ip=data.get("tailscale_ip", "N/A")
        )
        db.session.add(device)
        
    device.status = "Online"
    device.last_seen = now_str
    device.local_ip = data.get("local_ip", device.local_ip)
    device.tailscale_ip = data.get("tailscale_ip", device.tailscale_ip)
    db.session.commit()

    return jsonify({"status": "active", "server_time_ist": now_str})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
