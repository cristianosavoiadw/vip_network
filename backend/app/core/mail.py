"""Outgoing e-mail: one door for every message the platform sends.

Configured by the ``VIP_EMAIL_*`` settings (sender ``noreply@vipnetwork.com.br`` on the company
mail server, SMTP over SSL on 465). The password lives only in ``.env_dev`` / ``.env_prod``.
An admin form like BR Licitar's "Servidor de envio" can replace the environment later.

``provider`` empty means "log only": nothing leaves the machine (tests, dev without mail).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parseaddr

import aiosmtplib

from app.core.config import get_settings

log = logging.getLogger("vip.mail")


class MailError(Exception):
    """The server refused or could not be reached; the message is safe to log."""


@dataclass(frozen=True)
class MailConfig:
    provider: str
    sender: str
    reply_to: str
    host: str
    port: int
    security: str
    user: str
    password: str
    timeout: int

    @property
    def from_address(self) -> str:
        return parseaddr(self.sender)[1]

    @property
    def configured(self) -> bool:
        return self.provider == "smtp" and bool(self.host and self.from_address)


def config() -> MailConfig:
    s = get_settings()
    return MailConfig(
        provider=s.email_provider.strip().lower(),
        sender=s.email_from,
        reply_to=s.email_reply_to,
        host=s.email_smtp_host,
        port=s.email_smtp_port,
        security=s.email_smtp_security.strip().lower(),
        user=s.email_smtp_user,
        password=s.email_smtp_password,
        timeout=s.email_timeout_seconds,
    )


def _client(cfg: MailConfig) -> aiosmtplib.SMTP:
    return aiosmtplib.SMTP(
        hostname=cfg.host,
        port=cfg.port,
        use_tls=cfg.security == "ssl",
        start_tls=True if cfg.security == "starttls" else False,
        timeout=cfg.timeout,
    )


def build_message(
    *, to: str, subject: str, text: str, html: str | None, cfg: MailConfig
) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = cfg.sender
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=cfg.from_address.split("@")[-1] or "vipnetwork.com.br")
    if cfg.reply_to:
        msg["Reply-To"] = cfg.reply_to
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")
    return msg


async def send_mail(*, to: str, subject: str, text: str, html: str | None = None) -> bool:
    """Send one message. Returns False when mail is off (log only); raises MailError on failure."""
    cfg = config()
    if not cfg.configured:
        log.info("mail off (provider=%r): would send %r to %s", cfg.provider, subject, to)
        return False
    msg = build_message(to=to, subject=subject, text=text, html=html, cfg=cfg)
    try:
        async with _client(cfg) as smtp:
            if cfg.user:
                await smtp.login(cfg.user, cfg.password)
            await smtp.send_message(msg)
    except (aiosmtplib.SMTPException, OSError) as exc:
        raise MailError(f"{exc.__class__.__name__}: {exc}") from exc
    log.info("mail sent %r to %s", subject, to)
    return True


async def check_connection() -> str:
    """Connect and log in without sending anything. Returns the server greeting."""
    cfg = config()
    if not cfg.configured:
        raise MailError("E-mail desligado: defina VIP_EMAIL_PROVIDER=smtp e o servidor.")
    try:
        async with _client(cfg) as smtp:
            if cfg.user:
                await smtp.login(cfg.user, cfg.password)
            return f"{cfg.host}:{cfg.port} ({cfg.security}) · login {cfg.user or '-'} ok"
    except (aiosmtplib.SMTPException, OSError) as exc:
        raise MailError(f"{exc.__class__.__name__}: {exc}") from exc
