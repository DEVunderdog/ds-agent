from pathlib import Path
from typing import List, Optional

import emails
import structlog
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import settings

logger = structlog.get_logger(__name__)

template_dir = Path(__file__).parent.parent / "template"

env = Environment(
    loader=FileSystemLoader(template_dir),
    autoescape=select_autoescape(["html"]),
)


def send_email(
    *,
    email_to: str,
    subject: str,
    html_content: Optional[str],
):
    try:
        message = emails.Message(
            subject=subject,
            mail_from=(settings.FROM_NAME, settings.FROM_EMAIL),
            html=html_content,
        )

        smtp_options = {
            "host": settings.SMTP_HOST,
            "port": settings.SMTP_PORT,
        }

        if settings.SMTP_TLS:
            smtp_options["tls"] = True
        if settings.SMTP_USER:
            smtp_options["user"] = settings.SMTP_USER
        if settings.SMTP_PASSWORD:
            smtp_options["password"] = settings.SMTP_PASSWORD

        response = message.send(to=email_to, smtp=smtp_options)
        if response and response.status_code in [250, 200]:
            logger.info(
                f"email sent successfully to {email_to}, "
                f"response: {response.status_code}"
            )
        else:
            logger.exception(
                f"failed to send email to {email_to}, "
                f"response: {response.status_code if response else 'No response'}"
            )

    except Exception as e:
        logger.exception(f"exception while sending email to {email_to}: {e}")
        raise


def send_api_key_mail(email_to: List[str], api_key: str):
    try:
        template = env.get_template("mail_template.html")

        context = {
            "project_name": settings.FROM_NAME,
            "api_key": api_key,
        }

        html_content = template.render(context)

        subject = f"{settings.FROM_NAME} - API KEY"

        for mail in email_to:
            send_email(
                email_to=mail,
                subject=subject,
                html_content=html_content,
            )
            logger.info(f"api key email queued for sending it to {mail}")

    except Exception as e:
        logger.exception(f"error sending api key mails: {e}")
        raise
