import smtplib
from email.mime.text import MIMEText

# Your email settings
smtp_server = "smtp.gmail.com"
port = 587
sender_email = "your-email@gmail.com"
password = "adetomiwaoluwatobi45@gmail.com"
recipient = "recipient@example.com"

# Create a test message
msg = MIMEText("This is a test email")
msg['Subject'] = "Test Email"
msg['From'] = sender_email
msg['To'] = recipient

try:
    # Connect to the server
    server = smtplib.SMTP(smtp_server, port)
    server.starttls()  # Secure the connection
    print("Connected to server")
    
    # Log in
    server.login(sender_email, password)
    print("Logged in successfully")
    
    # Send email
    server.sendmail(sender_email, recipient, msg.as_string())
    print("Email sent successfully")
    
except Exception as e:
    print(f"Error: {e}")
    
finally:
    server.quit()