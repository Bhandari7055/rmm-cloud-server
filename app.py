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

GMAIL_USER = "Bhandaribharat216@gmail.com"
GMAIL_APP_PASSWORD = "otonfckjgfpndtfs"

def get_ist_now():
    return datetime.now(IST).strftime("%Y-%m-%d %I:%M:%S %p")

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
    admin_password = db.Column(db.String(100), default="Bhandari")

with app.app_context():
    try:
        db.create_all()
        if not SystemConfig.query.first():
            db.session.add(SystemConfig(admin_password="Bhandari"))
            db.session.commit()
    except Exception as e:
        print(f"DB Init Exception: {e}")

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
        admin_pass = config.admin_password if config else "Bhandari"

        if password == admin_pass:
            session['logged_in'] = True
            return jsonify({'status': 'success', 'message': 'Login successful!'})
        return jsonify({'status': 'error', 'message': 'Invalid Password'}), 401

    if session.get('logged_in'):
        return redirect(url_for('dashboard'))
    return render_template('dashboard.html', page="login", phone_number=GMAIL_USER)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    try:
        devices = SystemDevice.query.filter_by(is_removed=False).all()
        return render_template('dashboard.html', page="dashboard", devices=devices, phone_number=GMAIL_USER)
    except Exception as e:
        return f"Dashboard Error: {str(e)}", 500

@app.route('/send-otp', methods=['POST'])
def send_otp():
    try:
        otp = str(random.randint(100000, 999999))
        session['reset_otp'] = otp
        
        msg = MIMEText(f"Galaxy IT Monitor Pro - Password Reset OTP: {otp}\n\nIs OTP ko kisi ke sath share na karein.")
        msg['Subject'] = 'Galaxy RMM Admin Password Reset OTP'
        msg['From'] = GMAIL_USER
        msg['To'] = GMAIL_USER

        server = smtplib.SMTP('smtp.gmail.com', 587, timeout=15)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, [GMAIL_USER], msg.as_string())
        server.quit()

        return jsonify({'status': 'success', 'message': f'OTP sent successfully to {GMAIL_USER}'})

    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Gmail Send Failed: {str(e)}'}), 200

@app.route('/verify-otp-reset-password', methods=['POST'])
def verify_otp_reset():
    data = request.json or {}
    user_otp = data.get('otp')
    new_password = data.get('new_password')
    
    saved_otp = session.get('reset_otp')
    if not saved_otp or user_otp != saved_otp:
        return jsonify({'status': 'error', 'message': 'Invalid or expired OTP'}), 400
        
    config = SystemConfig.query.first()
    if config:
        config.admin_password = new_password
        db.session.commit()
        session.pop('reset_otp', None)
        return jsonify({'status': 'success', 'message': 'Password changed successfully!'})
    return jsonify({'status': 'error', 'message': 'System error'}), 500

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
