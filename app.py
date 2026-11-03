@app.route('/send-otp', methods=['POST'])
def send_otp():
    try:
        otp = str(random.randint(100000, 999999))
        session['reset_otp'] = otp
        
        # Render log me OTP show karega taaki aap reset kar sako
        print(f"\n==========================================")
        print(f"[GMAIL OTP FOR {GMAIL_USER}]: {otp}")
        print(f"==========================================\n")
        
        # Smtp connection (with short 3 sec timeout to prevent blocking UI)
        try:
            msg = MIMEText(f"Galaxy IT Monitor Pro OTP: {otp}")
            msg['Subject'] = 'Galaxy RMM Admin Password Reset OTP'
            msg['From'] = GMAIL_USER
            msg['To'] = GMAIL_USER
            
            server = smtplib.SMTP('smtp.gmail.com', 587, timeout=3)
            server.starttls()
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, [GMAIL_USER], msg.as_string())
            server.quit()
            return jsonify({'status': 'success', 'message': f'OTP sent to {GMAIL_USER}'})
        except Exception:
            # Fallback for Render SMTP block
            return jsonify({'status': 'success', 'message': f'OTP Generated! (Check Render Logs for OTP code)'})

    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Error: {str(e)}'}), 200
