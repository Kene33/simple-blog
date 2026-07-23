import asyncio
import smtplib
from email.message import EmailMessage

from src.core.config import Settings


def _send(settings: Settings, recipient: str, link: str) -> None:
    message = EmailMessage()
    message["Subject"] = "Reset your Simple Blog password"
    message["From"] = settings.smtp_from
    message["To"] = recipient
    message.set_content(f"Use this one-time link to reset your password:\n\n{link}\n")
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as client:
        if settings.smtp_starttls:
            client.starttls()
        if settings.smtp_username:
            password = "".join((settings.smtp_password or "").split())
            client.login(settings.smtp_username, password)
        client.send_message(message)


async def send_password_reset_email(settings: Settings, recipient: str, token: str) -> None:
    link = f"{settings.public_base_url.rstrip('/')}/password-reset?token={token}"
    await asyncio.to_thread(_send, settings, recipient, link)
