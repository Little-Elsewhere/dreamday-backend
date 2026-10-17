from email.message import EmailMessage
from email.utils import formataddr
from importlib.resources import files
from string import Template
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import aiosmtplib

from app.core.config import settings

EMAIL_TEMPLATES = files('app.templates.email')


async def send_verification_email(email: str, token: str) -> None:
  verification_url = urlsplit(str(settings.email_verification_url))
  query = dict(parse_qsl(verification_url.query, keep_blank_values=True))
  query['token'] = token
  link = urlunsplit(
    verification_url._replace(query=urlencode(query))
  )

  subject = EMAIL_TEMPLATES.joinpath('verification_subject.txt').read_text(
    encoding='utf-8'
  ).strip()
  body_template = EMAIL_TEMPLATES.joinpath('verification_body.txt').read_text(
    encoding='utf-8'
  )

  message = EmailMessage()
  message['From'] = formataddr(
    (settings.smtp_from_name, str(settings.smtp_from_email))
  )
  message['To'] = email
  message['Subject'] = subject
  message.set_content(
    Template(body_template).substitute(verification_link=link)
  )

  smtp_password = (
    settings.smtp_password.get_secret_value()
    if settings.smtp_password is not None
    and settings.smtp_password.get_secret_value()
    else None
  )
  await aiosmtplib.send(
    message,
    hostname=settings.smtp_host,
    port=settings.smtp_port,
    username=settings.smtp_username or None,
    password=smtp_password,
    use_tls=settings.smtp_use_tls,
    start_tls=settings.smtp_start_tls,
    timeout=settings.smtp_timeout_seconds,
  )
