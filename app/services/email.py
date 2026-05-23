import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import get_settings

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.settings = get_settings()

    def send_email(self, to_email: str, subject: str, body: str) -> bool:
        """
        Sends an email using SMTP settings from configuration.
        """
        if not self.settings.emails_enabled:
            logger.info(f"Email disabled. Would have sent to {to_email}: {subject}")
            return True

        if not self.settings.smtp_user or not self.settings.smtp_password:
            logger.warning("SMTP credentials not configured. Cannot send email.")
            return False

        try:
            msg = MIMEMultipart()
            msg['From'] = self.settings.smtp_user
            msg['To'] = to_email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))

            with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port) as server:
                server.starttls()
                server.login(self.settings.smtp_user, self.settings.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False

email_service = EmailService()
