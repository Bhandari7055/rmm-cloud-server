import socket

def send_otp_email(to_email, otp):
    msg = MIMEText(f"Your RMM Portal Password Reset OTP is: {otp}\nValid for 10 minutes.")
    msg['Subject'] = 'RMM Portal Password Reset OTP'
    msg['From'] = GMAIL_USER
    msg['To'] = to_email

    clean_pass = GMAIL_APP_PASS.replace(" ", "").strip()

    # Force IPv4 connection to prevent Render [Errno 101] Network Unreachable
    af_backup = socket.has_ipv6
    try:
        socket.has_ipv6 = False  # Disable IPv6 lookup
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=15)
        server.login(GMAIL_USER, clean_pass)
        server.sendmail(GMAIL_USER, [to_email], msg.as_string())
        server.quit()
        print(f"[SUCCESS] OTP Mail sent to {to_email}")
    finally:
        socket.has_ipv6 = af_backup
