import smtplib
from email.message import EmailMessage

from starlette.concurrency import run_in_threadpool

from app.infrastructure.settings import Settings


class SmtpMailer:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def password_reset(self, email: str, token: str) -> None:
        await run_in_threadpool(self._send, email, token)

    def _send(self, email: str, token: str) -> None:
        settings = self.settings
        message = EmailMessage()
        message["From"] = settings.mail_from
        message["To"] = email
        message["Subject"] = "Doce Maria — Recuperar senha / Reset password"
        message.set_content(
            "Use o codigo abaixo em 'Ja tenho o codigo' no aplicativo Doce Maria.\n"
            "Use the code below in 'I have a reset code' in the Doce Maria app.\n\n"
            f"{token}\n\n"
            f"Validade / Expires in: {settings.password_reset_minutes} minutos / minutes.\n"
            "Se voce nao solicitou, ignore este email. / "
            "If you did not request this, ignore this email.\n"
        )
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            if settings.smtp_starttls:
                server.starttls()
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password.get_secret_value())
            server.send_message(message)
