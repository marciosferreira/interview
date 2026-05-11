import os
import boto3
from botocore.exceptions import ClientError

_MOCK   = os.getenv("MOCK_EMAIL", "false").lower() == "true"
_REGION = os.getenv("SES_REGION", "us-east-1")
_FROM = os.getenv(key="SES_FROM_EMAIL", default="Acing Interviews <no_reply@acinginterviews.com>")
_BASE   = os.getenv("APP_BASE_URL", "http://localhost:8000").rstrip("/")
_CONTACT_FROM  = os.getenv("SES_CONTACT_EMAIL", "contact@acinginterviews.com")
_NOTIFY_TO     = os.getenv("ADMIN_NOTIFY_EMAIL", "marciosferreira@yahoo.com.br")

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


_VERIFY_COPY = {
    "en": {
        "subject": "Verify your acing interviews account",
        "heading": "Verify your email",
        "body":    "Click the button below to verify your email address.",
        "button":  "Verify my email",
        "footer":  "Link expires in 24 hours. If you didn't create an account, ignore this email.",
        "plain":   "Please verify your email by visiting:\n{link}\n\nThis link expires in 24 hours.",
    },
    "pt": {
        "subject": "Verifique sua conta no Acing Interview",
        "heading": "Verifique seu e-mail",
        "body":    "Clique no botão abaixo para verificar seu endereço de e-mail.",
        "button":  "Verificar meu e-mail",
        "footer":  "O link expira em 24 horas. Se você não criou uma conta, ignore este e-mail.",
        "plain":   "Por favor, verifique seu e-mail acessando:\n{link}\n\nEste link expira em 24 horas.",
    },
}

_RESET_COPY = {
    "en": {
        "subject": "Reset your acing interviews password",
        "heading": "Reset your password",
        "body":    "We received a password reset request for your account.",
        "button":  "Reset my password",
        "footer":  "Link expires in 15 minutes. If you didn't request this, ignore this email.",
        "plain":   "Reset your password by visiting:\n{link}\n\nThis link expires in 15 minutes.",
    },
    "pt": {
        "subject": "Redefina sua senha no Acing Interview",
        "heading": "Redefina sua senha",
        "body":    "Recebemos uma solicitação de redefinição de senha para sua conta.",
        "button":  "Redefinir minha senha",
        "footer":  "O link expira em 15 minutos. Se você não solicitou isso, ignore este e-mail.",
        "plain":   "Redefina sua senha acessando:\n{link}\n\nEste link expira em 15 minutos.",
    },
}


def _build_html(link: str, copy: dict) -> str:
    return f"""
<div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px">
  <h2 style="color:#6366f1">Acing Interviews</h2>
  <p>{copy['body']}</p>
  <a href="{link}" style="display:inline-block;margin:24px 0;padding:12px 28px;
     background:#6366f1;color:#fff;border-radius:10px;text-decoration:none;font-weight:600">
    {copy['button']}
  </a>
  <p style="color:#64748b;font-size:13px">{copy['footer']}</p>
</div>"""


def send_verification_email(to_email: str, token: str, language: str = "en") -> None:
    link = f"{_BASE}/verify-email.html?token={token}"
    copy = _VERIFY_COPY.get(language, _VERIFY_COPY["en"])
    _send(to_email, copy["subject"], _build_html(link, copy), copy["plain"].format(link=link))


def send_reset_email(to_email: str, token: str, language: str = "en") -> None:
    link = f"{_BASE}/reset-password.html?token={token}"
    copy = _RESET_COPY.get(language, _RESET_COPY["en"])
    _send(to_email, copy["subject"], _build_html(link, copy), copy["plain"].format(link=link))


def send_contact_notification(name: str, from_email: str, subject: str, body: str) -> None:
    notify_subject = f"[Contact] {subject}"
    text = f"New contact message from {name} <{from_email}>:\n\nSubject: {subject}\n\n{body}"
    html = f"""
<div style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:32px">
  <h2 style="color:#6366f1">New Contact Message — Acing Interviews</h2>
  <p><strong>From:</strong> {name} &lt;{from_email}&gt;</p>
  <p><strong>Subject:</strong> {subject}</p>
  <hr style="border:none;border-top:1px solid #2d3148;margin:16px 0"/>
  <p style="white-space:pre-wrap">{body}</p>
  <hr style="border:none;border-top:1px solid #2d3148;margin:16px 0"/>
  <p style="color:#64748b;font-size:13px">Reply via the admin panel: {_BASE}/admin-contact.html</p>
</div>"""
    _send(_NOTIFY_TO, notify_subject, html, text)


def send_contact_reply(to_email: str, to_name: str, original_subject: str, reply_text: str) -> None:
    reply_subject = f"Re: {original_subject}"
    text = f"Hello {to_name},\n\n{reply_text}\n\n---\nAcing Interview\n{_BASE}"
    html = f"""
<div style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:32px">
  <h2 style="color:#6366f1">Acing Interviews</h2>
  <p>Hello {to_name},</p>
  <p style="white-space:pre-wrap">{reply_text}</p>
  <hr style="border:none;border-top:1px solid #2d3148;margin:24px 0"/>
  <p style="color:#64748b;font-size:13px">acing interviews &mdash; <a href="{_BASE}" style="color:#6366f1">{_BASE}</a></p>
</div>"""
    if _MOCK:
        print(f"\n{'='*60}")
        print(f"[MOCK EMAIL] To: {to_email}")
        print(f"[MOCK EMAIL] Subject: {reply_subject}")
        print(f"[MOCK EMAIL] From: {_CONTACT_FROM}")
        print(f"[MOCK EMAIL] Body:\n{text}")
        print(f"{'='*60}\n")
        return
    try:
        resp = _get_ses().send_email(
            Source=_CONTACT_FROM,
            Destination={"ToAddresses": [to_email]},
            ReplyToAddresses=[_CONTACT_FROM],
            Message={
                "Subject": {"Data": reply_subject, "Charset": "UTF-8"},
                "Body": {
                    "Html": {"Data": html, "Charset": "UTF-8"},
                    "Text": {"Data": text, "Charset": "UTF-8"},
                },
            },
        )
        print(f"[SES] Reply sent to {to_email} | MessageId: {resp.get('MessageId')} | Subject: {reply_subject}")
    except Exception as exc:
        print(f"[SES] Failed to send reply to {to_email}: {exc}")
        raise
