import socket

@app.route('/send-otp', methods=['POST'])
def send_otp():
    try:
        otp = str(random.randint(100000, 999999))
        session['reset_otp'] = otp
        
        msg = MIMEText(f"Galaxy IT Monitor Pro - Password Reset OTP: {otp}\n\nIs OTP ko kisi ke sath share na karein.")
        msg['Subject'] = 'Galaxy RMM Admin Password Reset OTP'
        msg['From'] = GMAIL_USER
        msg['To'] = GMAIL_USER

        # Render specific: Bypass IPv6 network unreachable error via explicit IPv4 connection
        smtp_host = "smtp.gmail.com"
        smtp_port = 587

        # Force IPv4 resolution
        addr_info = socket.getaddrinfo(smtp_host, smtp_port, socket.AF_INET, socket.SOCK_STREAM)
        ipv4_ip = addr_info[0][4][0]

        # Connect directly to Gmail IPv4
        server = smtplib.SMTP(ipv4_ip, smtp_port, timeout=20)
        server.ehlo(smtp_host)
        server.starttls()
        server.ehlo(smtp_host)
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, [GMAIL_USER], msg.as_string())
        server.quit()

        return jsonify({'status': 'success', 'message': f'OTP sent successfully to {GMAIL_USER}'})

    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Gmail Send Failed: {str(e)}'}), 200
