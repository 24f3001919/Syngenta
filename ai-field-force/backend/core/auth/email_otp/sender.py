"""
Email OTP sender — sends 6-digit codes for 2FA on login.

Two implementations:
  - ConsoleEmailSender: prints to stdout (dev fallback when SMTP not configured)
  - SmtpEmailSender:    real outgoing email via SMTP (Gmail in our setup)

The factory below auto-picks based on whether SMTP env vars are present.
"""
from __future__ import annotations

import logging
import smtplib
import ssl
from abc import ABC, abstractmethod
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import (
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USER,
    SMTP_PASSWORD,
    SMTP_FROM,
    EMAIL_OTP_DEMO_REDIRECT,
    OTP_EMAIL_EXPIRY_SECONDS,
)

logger = logging.getLogger(__name__)


# ─── HTML template ────────────────────────────────────────────────────────────

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f0f7f0; padding: 32px;">
  <table cellpadding="0" cellspacing="0" style="max-width: 480px; margin: 0 auto; background: white; border-radius: 16px; padding: 32px; box-shadow: 0 4px 24px rgba(0,0,0,0.08);">
    <tr><td>
      <div style="font-size: 12px; color: #4a7c5e; letter-spacing: 0.15em; font-weight: 700; text-transform: uppercase; margin-bottom: 12px;">Kheti Compass</div>
      <h1 style="margin: 0 0 16px; font-size: 24px; color: #1a3a2a; font-weight: 700;">Your sign-in code</h1>
      <p style="margin: 0 0 24px; color: #4a5568; line-height: 1.6;">Enter this code in the app to complete your login. It expires in {expiry_minutes} minutes.</p>
      <div style="background: #f0f7f0; border-radius: 12px; padding: 24px; text-align: center; margin-bottom: 24px;">
        <div style="font-family: 'SF Mono', Menlo, monospace; font-size: 36px; letter-spacing: 0.3em; color: #1a3a2a; font-weight: 700;">{code}</div>
      </div>
      <p style="margin: 0 0 8px; font-size: 13px; color: #718096;">If you didn't request this code, you can safely ignore this email.</p>
      <p style="margin: 16px 0 0; font-size: 12px; color: #a0aec0;">Originally addressed to: {original_email}</p>
    </td></tr>
  </table>
</body>
</html>
"""

_TEXT_TEMPLATE = """\
Kheti Compass — sign-in code

Enter this code in the app to complete your login:

   {code}

It expires in {expiry_minutes} minutes.

Originally addressed to: {original_email}
If you didn't request this code, ignore this email.
"""


# ─── Base ─────────────────────────────────────────────────────────────────────

class EmailSender(ABC):
    name: str = "abstract"

    @abstractmethod
    def send(self, *, to: str, code: str, original_email: str) -> bool:
        """Send the OTP code to `to`. `original_email` is included in the body
        so the user knows which account they're logging into when demo
        redirect rewrites the destination. Returns True on success."""
        ...


# ─── Console (fallback) ───────────────────────────────────────────────────────

class ConsoleEmailSender(EmailSender):
    name = "console"

    def send(self, *, to: str, code: str, original_email: str) -> bool:
        print("─" * 60)
        print(f"  [EMAIL OTP / console] to={to} (originally {original_email})")
        print(f"  CODE: {code}")
        print(f"  expires in {OTP_EMAIL_EXPIRY_SECONDS // 60} min")
        print("─" * 60)
        return True


# ─── SMTP (Gmail or any compliant server) ─────────────────────────────────────

class SmtpEmailSender(EmailSender):
    name = "smtp"

    def send(self, *, to: str, code: str, original_email: str) -> bool:
        expiry_minutes = max(1, OTP_EMAIL_EXPIRY_SECONDS // 60)

        message = MIMEMultipart("alternative")
        message["Subject"] = f"{code} — your Kheti Compass sign-in code"
        message["From"]    = SMTP_FROM
        message["To"]      = to

        text_part = MIMEText(
            _TEXT_TEMPLATE.format(
                code=code,
                expiry_minutes=expiry_minutes,
                original_email=original_email,
            ),
            "plain",
        )
        html_part = MIMEText(
            _HTML_TEMPLATE.format(
                code=code,
                expiry_minutes=expiry_minutes,
                original_email=original_email,
            ),
            "html",
        )
        message.attach(text_part)
        message.attach(html_part)

        try:
            context = ssl.create_default_context()
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                server.starttls(context=context)
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(message)
            logger.info("Email OTP sent to %s (originally %s)", to, original_email)
            return True
        except Exception as exc:
            logger.exception("SMTP send failed: %s", exc)
            return False


# ─── Factory ──────────────────────────────────────────────────────────────────

def _build_sender() -> EmailSender:
    if SMTP_USER and SMTP_PASSWORD:
        return SmtpEmailSender()
    return ConsoleEmailSender()


email_sender: EmailSender = _build_sender()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def resolve_destination(original_email: str) -> str:
    """If a demo-redirect is configured AND the user's email matches a demo
    domain, route the OTP to the configured demo inbox instead. Returns the
    actual `to` address used.
    """
    if not EMAIL_OTP_DEMO_REDIRECT:
        return original_email
    # Redirect any demo-domain emails to the dev inbox
    domain = original_email.split("@")[-1].lower() if "@" in original_email else ""
    if domain in ("syngenta.com", "example.com", "demo.local"):
        return EMAIL_OTP_DEMO_REDIRECT
    return original_email


def mask_email(email: str) -> str:
    """Return a privacy-safe masked version for display, e.g.
    'manager@syngenta.com' -> 'm******@s********.com'."""
    if not email or "@" not in email:
        return "***"
    local, _, domain = email.partition("@")
    masked_local = local[0] + "*" * max(1, len(local) - 1)
    parts = domain.split(".")
    masked_domain_main = parts[0][0] + "*" * max(1, len(parts[0]) - 1)
    return f"{masked_local}@{masked_domain_main}." + ".".join(parts[1:])