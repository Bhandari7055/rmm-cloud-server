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

        # Port 587 (STARTTLS) with explicit IPv4 fallback
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
