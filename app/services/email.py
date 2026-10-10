import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings

class EmailService:
    def __init__(self):
        self.sender_email = settings.MAIL_USERNAME
        self.sender_password = settings.MAIL_PASSWORD
        self.smtp_server = settings.MAIL_HOST
        self.smtp_port = settings.MAIL_PORT
        
    def send_registration_email(self, to_email: str, access_code: str, school_name: str):
        if not self.sender_email or not self.sender_password:
            print("Email credentials not configured. Skipping email.")
            return

        message = MIMEMultipart("alternative")
        message["Subject"] = "Welcome to Millionaires on Wheels - Your Access Code"
        message["From"] = f"Millionaires on Wheels <{self.sender_email}>"
        message["To"] = to_email

        text = f"Hello {school_name},\n\nWelcome to Millionaires on Wheels!\nYour registration was successful.\n\nYour secure access code is: {access_code}\n\nUse this code to access your Team Dashboard.\n\nBest regards,\nMillionaires on Wheels Team"
        
        html = f"""
        <html>
          <body>
            <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #2E7D32;">Welcome to Millionaires on Wheels!</h2>
                <p>Hello <strong>{school_name}</strong>,</p>
                <p>Your registration was successful.</p>
                <p>Your secure access code is:</p>
                <div style="background-color: #f3f4f6; padding: 20px; text-align: center; border-radius: 10px; margin: 20px 0;">
                    <span style="font-size: 32px; font-weight: bold; letter-spacing: 4px; font-family: monospace; color: #1f2937;">{access_code}</span>
                </div>
                <p>Use this code to access your Team Dashboard later.</p>
                <br>
                <p>Best regards,<br>Millionaires on Wheels Team</p>
            </div>
          </body>
        </html>
        """
        
        part1 = MIMEText(text, "plain")
        part2 = MIMEText(html, "html")
        message.attach(part1)
        message.attach(part2)

        try:
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.sender_email, self.sender_password)
            server.sendmail(self.sender_email, to_email, message.as_string())
            server.quit()
            print(f"Successfully sent registration email to {to_email}")
        except Exception as e:
            print(f"Failed to send email to {to_email}: {e}")

    def send_email(self, to_email: str, subject: str, body: str):
        if not self.sender_email or not self.sender_password:
            print("Email credentials not configured. Skipping email.")
            return

        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"Millionaires on Wheels <{self.sender_email}>"
        message["To"] = to_email

        html = body
        # Simple plain text fallback
        text = body.replace("<br>", "\n").replace("</p>", "\n").replace("</li>", "\n")
        import re
        text = re.sub(r'<[^>]+>', '', text)

        part1 = MIMEText(text, "plain")
        part2 = MIMEText(html, "html")
        message.attach(part1)
        message.attach(part2)

        try:
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.sender_email, self.sender_password)
            server.sendmail(self.sender_email, to_email, message.as_string())
            server.quit()
            print(f"Successfully sent email to {to_email}")
        except Exception as e:
            print(f"Failed to send email to {to_email}: {e}")

email_service = EmailService()
