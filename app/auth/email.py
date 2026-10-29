from email.message import EmailMessage
from email.utils import formataddr
from importlib.resources import files
from string import Template
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import aiosmtplib
from pydantic import AnyHttpUrl

from app.core.config import settings

EMAIL_TEMPLATES = files('app.auth.templates.email')


async def send_verification_email(email: str, token: str) -> None:
  await _send_link_email(
    email=email,
    token=token,
    page_url=settings.email_verification_url,
    subject_name='verification_subject.txt',
    body_name='verification_body.txt',
    link_key='verification_link',
  )


async def send_password_reset_email(email: str, token: str) -> None:
  await _send_link_email(
    email=email,
    token=token,
    page_url=settings.password_reset_url,
    subject_name='password_reset_subject.txt',
    body_name='password_reset_body.txt',
    link_key='password_reset_link',
  )


async def _send_link_email(
  *,
  email: str,
  token: str,
  page_url: AnyHttpUrl,
  subject_name: str,
  body_name: str,
  link_key: str,
) -> None:
  page = urlsplit(str(page_url))
  query = dict(parse_qsl(page.query, keep_blank_values=True))
  query['token'] = token
  link = urlunsplit(page._replace(query=urlencode(query)))

  subject = (
    EMAIL_TEMPLATES.joinpath(subject_name).read_text(encoding='utf-8').strip()
  )
  body_template = EMAIL_TEMPLATES.joinpath(body_name).read_text(
    encoding='utf-8'
  )

  message = EmailMessage()
  message['From'] = formataddr(
    (settings.smtp_from_name, str(settings.smtp_from_email))
  )
  message['To'] = email
  message['Subject'] = subject
  message.set_content(Template(body_template).substitute({link_key: link}))

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
