import os
import boto3
from botocore.exceptions import ClientError

_MOCK   = os.getenv("MOCK_EMAIL", "false").lower() == "true"
_REGION = os.getenv("SES_REGION", "us-east-1")
_FROM   = os.getenv("SES_FROM_EMAIL", "noreply@yourdomain.com")
_BASE   = os.getenv("APP_BASE_URL", "http://localhost:8000").rstrip("/")

_ses = None


def _get_ses():
    global _ses
    if _ses is None:
        _ses = boto3.client("ses", region_name=_REGION)
    return _ses


def _send(to: str, subject: str, html: str, text: str) -> None:
    if _MOCK:
        print(f"\n{'='*60}")
        print(f"[MOCK EMAIL] To: {to}")
        print(f"[MOCK EMAIL] Subject: {subject}")
        print(f"[MOCK EMAIL] Body:\n{text}")
        print(f"{'='*60}\n")
        return
    try:
        _get_ses().send_email(
            Source=_FROM,
            Destination={"ToAddresses": [to]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Html": {"Data": html, "Charset": "UTF-8"},
                    "Text": {"Data": text, "Charset": "UTF-8"},
                },
            },
        )
    except ClientError as exc:
        print(f"[SES] Failed to send email to {to}: {exc}")
        raise


def send_verification_email(to_email: str, token: str) -> None:
    link = f"{_BASE}/verify-email.html?token={token}"
    subject = "Verify your Interview Coach account"
    text = f"Please verify your email by visiting:\n{link}\n\nThis link expires in 24 hours."
    html = f"""
<div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px">
  <h2 style="color:#6366f1">Interview Coach</h2>
  <p>Click the button below to verify your email address.</p>
  <a href="{link}" style="display:inline-block;margin:24px 0;padding:12px 28px;
     background:#6366f1;color:#fff;border-radius:10px;text-decoration:none;font-weight:600">
    Verify my email
  </a>
  <p style="color:#64748b;font-size:13px">Link expires in 24 hours. If you didn't create an account, ignore this email.</p>
</div>"""
    _send(to_email, subject, html, text)


def send_reset_email(to_email: str, token: str) -> None:
    link = f"{_BASE}/reset-password.html?token={token}"
    subject = "Reset your Interview Coach password"
    text = f"Reset your password by visiting:\n{link}\n\nThis link expires in 15 minutes."
    html = f"""
<div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px">
  <h2 style="color:#6366f1">Interview Coach</h2>
  <p>We received a password reset request for your account.</p>
  <a href="{link}" style="display:inline-block;margin:24px 0;padding:12px 28px;
     background:#6366f1;color:#fff;border-radius:10px;text-decoration:none;font-weight:600">
    Reset my password
  </a>
  <p style="color:#64748b;font-size:13px">Link expires in 15 minutes. If you didn't request this, ignore this email.</p>
</div>"""
    _send(to_email, subject, html, text)
