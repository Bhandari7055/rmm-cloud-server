import os

@app.route('/send-otp', methods=['POST'])
def send_otp():
    try:
        otp = str(random.randint(100000, 999999))
        session['reset_otp'] = otp
        
        # API Key read cleanly
        brevo_key = os.environ.get("BREVO_API_KEY", "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")
        
        url = "https://api.brevo.com/v3/smtp/email"
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "api-key": brevo_key
        }
        payload = {
            "sender": {"name": "Galaxy IT Monitor Pro", "email": "Bhandaribharat216@gmail.com"},
            "to": [{"email": GMAIL_USER, "name": "Admin"}],
            "subject": "Galaxy RMM Admin Password Reset OTP",
            "htmlContent": f"<h3>Galaxy IT Monitor Pro</h3><p>Aapka Password Reset OTP hai: <b>{otp}</b></p><p>Is OTP ko kisi ke sath share na karein.</p>"
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code in [200, 201]:
            return jsonify({'status': 'success', 'message': f'OTP successfully sent to {GMAIL_USER}'})
        else:
            return jsonify({'status': 'error', 'message': f'Email API Error: {response.text}'}), 200

    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Send Failed: {str(e)}'}), 200
