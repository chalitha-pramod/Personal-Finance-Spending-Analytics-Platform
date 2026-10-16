import smtplib
from email.message import EmailMessage

from flask import current_app


def send_reset_email(recipient, reset_url):
    message = EmailMessage()
    message["Subject"] = "Reset your finance account password"
    message["From"] = current_app.config["MAIL_FROM"]
    message["To"] = recipient
    message.set_content(
        f"A password reset was requested. This link expires in 30 minutes:\n\n{reset_url}\n\n"
        "If you did not request it, you can ignore this message."
    )
    with smtplib.SMTP(current_app.config["MAIL_HOST"], current_app.config["MAIL_PORT"], timeout=10) as smtp:
        if current_app.config["MAIL_USE_TLS"]:
            smtp.starttls()
        if current_app.config["MAIL_USERNAME"]:
            smtp.login(current_app.config["MAIL_USERNAME"], current_app.config["MAIL_PASSWORD"])
        smtp.send_message(message)
