import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart, MIMEBase

SMTP_SERVER_HOST = 'localhost'
SMTP_SERVER_PORT = 1025
SENDER_ADDRESS = 'jaindevansh804@gmail.com'
SENDER_PASSWORD = ''

def send_email(to, subject, body, html=None):
    # Create a MIMEMultipart email message
    msg = MIMEMultipart()
    msg['From'] = SENDER_ADDRESS
    msg['To'] = to
    msg['Subject'] = subject
    msg['HTML'] = html

    # Attach the email body as HTML content
    msg.attach(MIMEText(body, 'html'))  # Pass `body`, not `msg`
    msg.attach(MIMEText(html, 'html'))  # Pass `html`, not `body`

    try:
        with smtplib.SMTP(SMTP_SERVER_HOST, SMTP_SERVER_PORT) as server:
            server.login(SENDER_ADDRESS, SENDER_PASSWORD)
            server.send_message(msg)
        print(f"Email sent to {to}")
        return True
    
    except Exception as e:
        print(f"Error sending email: {e}")
        return False