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

    def _send_mime(self, to_email: str, message: MIMEMultipart) -> bool:
        if not self.sender_email or not self.sender_password:
            print(f"[EmailService] Email credentials not configured. Skipping email to {to_email}.")
            return False

        try:
            server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=15)
            server.starttls()
            server.login(self.sender_email, self.sender_password)
            server.sendmail(self.sender_email, to_email, message.as_string())
            server.quit()
            print(f"[EmailService] Successfully sent email to {to_email}")
            return True
        except Exception as e:
            print(f"[EmailService] Failed to send email to {to_email}: {e}")
            return False

    def send_verification_email(self, to_email: str, access_code: str, school_name: str):
        """Step 1 Email: Sent immediately upon registration to verify the school's email address."""
        message = MIMEMultipart("alternative")
        message["Subject"] = f"Verify Your School Email: {access_code} - Who Wants To be A Scholarnnaire"
        message["From"] = f"Who Wants To be A Scholarnnaire <{self.sender_email}>"
        message["To"] = to_email

        text = (
            f"Hello {school_name},\n\n"
            f"Thank you for registering your school for the Who Wants To be A Scholarnnaire National Academic Championship.\n\n"
            f"Your 6-Digit Email Verification Code is: {access_code}\n\n"
            f"Enter this code on the registration verification screen to activate your account.\n\n"
            f"If you did not initiate this registration, please disregard this email.\n\n"
            f"Best regards,\n"
            f"Who Wants To be A Scholarnnaire Championship Committee\n"
            f"https://scholarnnaire.com"
        )

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8">
          <style>
            body {{ font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; color: #1e293b; margin: 0; padding: 20px; }}
            .container {{ max-width: 580px; margin: 0 auto; background: #ffffff; border-radius: 16px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); }}
            .header {{ background: #0f172a; padding: 32px 24px; text-align: center; color: #ffffff; }}
            .badge {{ display: inline-block; padding: 4px 12px; background: rgba(16, 185, 129, 0.2); border: 1px solid #10b981; color: #34d399; border-radius: 9999px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 12px; }}
            .content {{ padding: 32px 28px; }}
            .code-box {{ background: #f0fdf4; border: 2px dashed #10b981; border-radius: 12px; padding: 24px; text-align: center; margin: 28px 0; }}
            .code {{ font-size: 38px; font-weight: 800; letter-spacing: 6px; font-family: ui-monospace, Menlo, Monaco, Consolas, monospace; color: #047857; }}
            .footer {{ background: #f8fafc; padding: 20px 24px; text-align: center; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0; }}
          </style>
        </head>
        <body>
          <div class="container">
            <div class="header">
              <span class="badge">National Academic Championship</span>
              <h1 style="margin: 0; font-size: 24px; font-weight: 800; letter-spacing: -0.025em;">Email Verification</h1>
            </div>
            <div class="content">
              <p style="font-size: 16px; line-height: 1.6; margin-top: 0;">Hello <strong>{school_name}</strong>,</p>
              <p style="font-size: 15px; line-height: 1.6; color: #475569;">
                Thank you for enrolling your institution in the <strong>Who Wants To be A Scholarnnaire</strong> National High School Academic Championship.
              </p>
              <p style="font-size: 15px; line-height: 1.6; color: #475569;">
                Please enter the 6-digit verification code below on the screen to confirm your official institutional email address:
              </p>

              <div class="code-box">
                <div style="font-size: 12px; font-weight: 600; color: #065f46; text-transform: uppercase; margin-bottom: 6px; letter-spacing: 0.05em;">Your Verification Code</div>
                <div class="code">{access_code}</div>
              </div>

              <p style="font-size: 13px; color: #64748b; line-height: 1.5;">
                Once verified, your school administration account will be unlocked and you will receive your official administrative login credentials and onboarding guide.
              </p>
            </div>
            <div class="footer">
              <p style="margin: 0 0 6px 0;">Who Wants To be A Scholarnnaire Academic Championship</p>
              <p style="margin: 0;"><a href="https://scholarnnaire.com" style="color: #059669; text-decoration: none;">https://scholarnnaire.com</a></p>
            </div>
          </div>
        </body>
        </html>
        """

        part1 = MIMEText(text, "plain")
        part2 = MIMEText(html, "html")
        message.attach(part1)
        message.attach(part2)
        return self._send_mime(to_email, message)

    def send_registration_email(self, to_email: str, access_code: str, school_name: str):
        """Backward-compatibility alias for send_verification_email."""
        return self.send_verification_email(to_email, access_code, school_name)

    def send_school_onboarding_email(self, to_email: str, school_name: str, admin_username: str):
        """Step 2 Email: Sent immediately after email verification completes, with portal login credentials and administration instructions."""
        message = MIMEMultipart("alternative")
        message["Subject"] = f"Account Verified: School Administration Credentials & Guide - {school_name}"
        message["From"] = f"Who Wants To be A Scholarnnaire <{self.sender_email}>"
        message["To"] = to_email

        login_url = "https://scholarnnaire.com/login?tab=school"

        text = (
            f"Congratulations {school_name}!\n\n"
            f"Your institutional registration for the Who Wants To be A Scholarnnaire National Academic Championship has been successfully verified.\n\n"
            f"Your School Administration Credentials:\n"
            f"- Portal Login URL: {login_url}\n"
            f"- Admin Username: {admin_username}\n"
            f"- Registered Email: {to_email}\n"
            f"- Password: (The secure password created during registration)\n\n"
            f"Next Steps to Administer Your School:\n"
            f"1. Log In to School Admin Portal: Go to {login_url} and sign in under the 'School Admin' tab.\n"
            f"2. Enroll Your Student Squad: Register your official student contestants (3 to 5 delegates) with their subject specialties.\n"
            f"3. Nominate Team Captain: Designate an official Team Captain who will receive their live buzzer tournament Participant ID.\n"
            f"4. View Tournament Tracks & Match Schedules: Access fixture dates, rules, syllabus coverage, and leaderboard standings.\n\n"
            f"Need assistance? Contact our Tournament Coordination Team at info@scholarnnaire.com.\n\n"
            f"Best regards,\n"
            f"Who Wants To be A Scholarnnaire Academic Championship\n"
            f"https://scholarnnaire.com"
        )

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8">
          <style>
            body {{ font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; color: #1e293b; margin: 0; padding: 20px; }}
            .container {{ max-width: 620px; margin: 0 auto; background: #ffffff; border-radius: 16px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); }}
            .header {{ background: #0f172a; padding: 32px 28px; text-align: center; color: #ffffff; }}
            .badge {{ display: inline-block; padding: 4px 12px; background: rgba(16, 185, 129, 0.2); border: 1px solid #10b981; color: #34d399; border-radius: 9999px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 12px; }}
            .content {{ padding: 32px 28px; }}
            .creds-card {{ background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 12px; padding: 20px 24px; margin: 24px 0; }}
            .creds-row {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #e2e8f0; font-size: 14px; }}
            .creds-row:last-child {{ border-bottom: none; }}
            .creds-label {{ color: #64748b; font-weight: 600; }}
            .creds-value {{ color: #0f172a; font-weight: 700; font-family: ui-monospace, Menlo, Monaco, Consolas, monospace; }}
            .button {{ display: block; text-align: center; background: #059669; color: #ffffff !important; padding: 14px 28px; border-radius: 10px; font-weight: 700; font-size: 15px; text-decoration: none; margin: 24px 0; }}
            .step-list {{ margin: 20px 0; padding-left: 0; list-style: none; }}
            .step-item {{ display: flex; margin-bottom: 16px; font-size: 14px; line-height: 1.5; }}
            .step-num {{ width: 24px; height: 24px; border-radius: 50%; background: #059669; color: #ffffff; font-weight: 700; display: inline-flex; align-items: center; justify-content: center; font-size: 12px; margin-right: 12px; flex-shrink: 0; text-align: center; line-height: 24px; }}
            .footer {{ background: #f8fafc; padding: 20px 28px; text-align: center; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0; }}
          </style>
        </head>
        <body>
          <div class="container">
            <div class="header">
              <span class="badge">Registration Verified ✓</span>
              <h1 style="margin: 0; font-size: 24px; font-weight: 800; letter-spacing: -0.025em;">Welcome to the Championship</h1>
            </div>
            <div class="content">
              <p style="font-size: 16px; line-height: 1.6; margin-top: 0;">Congratulations <strong>{school_name}</strong>,</p>
              <p style="font-size: 15px; line-height: 1.6; color: #475569;">
                Your institutional email address has been successfully verified! Your official School Administration account is now fully active for the <strong>Who Wants To be A Scholarnnaire</strong> Tournament.
              </p>

              <div class="creds-card">
                <div style="font-size: 13px; font-weight: 700; color: #0f172a; text-transform: uppercase; margin-bottom: 12px; letter-spacing: 0.05em;">Your School Administration Credentials</div>
                <div class="creds-row">
                  <span class="creds-label">Admin Username:</span>
                  <span class="creds-value">{admin_username}</span>
                </div>
                <div class="creds-row">
                  <span class="creds-label">Registered Contact Email:</span>
                  <span class="creds-value">{to_email}</span>
                </div>
                <div class="creds-row">
                  <span class="creds-label">Password:</span>
                  <span class="creds-value" style="font-family: inherit; font-size: 13px; color: #64748b;">(Created during registration)</span>
                </div>
              </div>

              <a href="{login_url}" class="button">Access School Administration Portal →</a>

              <h3 style="font-size: 16px; font-weight: 700; color: #0f172a; margin: 28px 0 12px 0;">How to Administer Your School Team:</h3>
              <div class="step-list">
                <div class="step-item">
                  <span class="step-num">1</span>
                  <div><strong>Log In to Your Console:</strong> Visit the portal and sign in under the <em>School Admin</em> tab using your username <code>{admin_username}</code>.</div>
                </div>
                <div class="step-item">
                  <span class="step-num">2</span>
                  <div><strong>Register Your Student Delegates:</strong> Enroll 3 to 5 eligible student contestants under Junior or Senior secondary categories with their subject specialties.</div>
                </div>
                <div class="step-item">
                  <span class="step-num">3</span>
                  <div><strong>Nominate Team Captain:</strong> Assign a Team Captain. Each contestant automatically receives an official Participant ID for the live buzzer competition arena.</div>
                </div>
                <div class="step-item">
                  <span class="step-num">4</span>
                  <div><strong>Track Schedules & Standings:</strong> View upcoming tournament stages, preliminary qualifiers, and live leaderboard rankings across all 36 states.</div>
                </div>
              </div>

              <div style="background: #f1f5f9; border-radius: 10px; padding: 14px 18px; font-size: 13px; color: #475569; margin-top: 24px;">
                <strong>Need Support?</strong> If you require assistance with roster setup or technical inquiries, contact our coordination desk at <a href="mailto:info@scholarnnaire.com" style="color: #059669; font-weight: 600;">info@scholarnnaire.com</a>.
              </div>
            </div>
            <div class="footer">
              <p style="margin: 0 0 6px 0;">Who Wants To be A Scholarnnaire Academic Championship</p>
              <p style="margin: 0;"><a href="https://scholarnnaire.com" style="color: #059669; text-decoration: none;">https://scholarnnaire.com</a></p>
            </div>
          </div>
        </body>
        </html>
        """

        part1 = MIMEText(text, "plain")
        part2 = MIMEText(html, "html")
        message.attach(part1)
        message.attach(part2)
        return self._send_mime(to_email, message)

    def send_email(self, to_email: str, subject: str, body: str):
        if not self.sender_email or not self.sender_password:
            print("[EmailService] Email credentials not configured. Skipping email.")
            return False

        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"Who Wants To be A Scholarnnaire <{self.sender_email}>"
        message["To"] = to_email

        html = body
        import re
        text = re.sub(r'<[^>]+>', '', body.replace("<br>", "\n").replace("</p>", "\n").replace("</li>", "\n"))

        part1 = MIMEText(text, "plain")
        part2 = MIMEText(html, "html")
        message.attach(part1)
        message.attach(part2)
        return self._send_mime(to_email, message)

email_service = EmailService()
