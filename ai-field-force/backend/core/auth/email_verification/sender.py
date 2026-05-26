"""
Verification-email sender.

Reuses the same transport layer as the OTP sender (Resend → SMTP → console)
but with a different template: a CTA button linking to the frontend's
/verify-email?token=<token> page instead of a code block.
"""
from __future__ import annotations

import logging

import requests

from config import (
    RESEND_API_KEY,
    RESEND_FROM,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USER,
    SMTP_FROM,
)

logger = logging.getLogger(__name__)

# ─── HTML template ─────────────────────────────────────────────────────────────

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f0f7f0; padding: 32px;">
  <table cellpadding="0" cellspacing="0" style="max-width: 480px; margin: 0 auto; background: white; border-radius: 16px; padding: 32px; box-shadow: 0 4px 24px rgba(0,0,0,0.08);">
    <tr><td>
      <div style="font-size: 12px; color: #4a7c5e; letter-spacing: 0.15em; font-weight: 700; text-transform: uppercase; margin-bottom: 12px;">Kheti Compass</div>
      <h1 style="margin: 0 0 16px; font-size: 24px; color: #1a3a2a; font-weight: 700;">Verify your email address</h1>
      <p style="margin: 0 0 24px; color: #4a5568; line-height: 1.6;">
        Thanks for registering! Click the button below to confirm your email address and activate your account.
        This link expires in <strong>24 hours</strong>.
      </p>
      <div style="text-align: center; margin-bottom: 28px;">
        <a href="{verify_url}"
           style="display: inline-block; background: #2d6a4f; color: white; text-decoration: none;
                  font-weight: 700; font-size: 16px; padding: 14px 32px; border-radius: 10px;
                  letter-spacing: 0.02em;">
          Verify my email
        </a>
      </div>
      <p style="margin: 0 0 8px; font-size: 13px; color: #718096;">
        Or copy this link into your browser:
      </p>
      <p style="margin: 0 0 20px; font-size: 12px; color: #4a7c5e; word-break: break-all;">{verify_url}</p>
      <p style="margin: 0; font-size: 13px; color: #718096;">
        If you didn't create a Kheti Compass account, you can safely ignore this email.
      </p>
    </td></tr>
  </table>
</body>
</html>
"""

_TEXT_TEMPLATE = """\
Kheti Compass — verify your email address

Thanks for registering! Visit the link below to confirm your email address.
This link expires in 24 hours.

{verify_url}

If you didn't create a Kheti Compass account, ignore this email.
"""

_SUBJECT = "Verify your email for Kheti Compass"


# ─── Transport (mirrors OTP sender priority: Resend → SMTP → console) ─────────

def send_verification_email(to: str, token: str, frontend_base_url: str) -> bool:
    """Send a verification link email. Returns True on success."""
    verify_url = f"{frontend_base_url.rstrip('/')}/verify-email?token={token}"
    html_body = _HTML_TEMPLATE.format(verify_url=verify_url)
    text_body = _TEXT_TEMPLATE.format(verify_url=verify_url)

    if RESEND_API_KEY:
        return _send_via_resend(to, html_body, text_body)
    if SMTP_USER and SMTP_PASSWORD:
        return _send_via_smtp(to, html_body, text_body)
    return _send_via_console(to, verify_url)


def _send_via_resend(to: str, html_body: str, text_body: str) -> bool:
    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from":    RESEND_FROM,
                "to":      [to],
                "subject": _SUBJECT,
                "html":    html_body,
                "text":    text_body,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            logger.info("Verification email sent via Resend to %s", to)
            return True
        logger.error("Resend verification failed: status=%s body=%s", resp.status_code, resp.text[:300])
        return False
    except Exception as exc:
        logger.exception("Resend verification request failed: %s", exc)
        return False


def _send_via_smtp(to: str, html_body: str, text_body: str) -> bool:
    import smtplib
    import ssl
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    message = MIMEMultipart("alternative")
    message["Subject"] = _SUBJECT
    message["From"]    = SMTP_FROM
    message["To"]      = to
    message.attach(MIMEText(text_body, "plain"))
    message.attach(MIMEText(html_body, "html"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls(context=context)
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(message)
        logger.info("Verification email sent via SMTP to %s", to)
        return True
    except Exception as exc:
        logger.exception("SMTP verification send failed: %s", exc)
        return False


def _send_via_console(to: str, verify_url: str) -> bool:
    print("─" * 60)
    print(f"  [EMAIL VERIFY / console] to={to}")
    print(f"  LINK: {verify_url}")
    print("─" * 60)
    return True