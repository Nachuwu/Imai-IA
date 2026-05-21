"""
Gmail por voz — leer correos y enviar mensajes.
Usa las mismas credenciales OAuth que Google Calendar (data/calendar_credentials.json).
El token se guarda por separado en data/gmail_token.json.
"""
import os
import re
import base64
from email.mime.text import MIMEText

from config import GMAIL_ENABLED

_ROOT       = os.path.join(os.path.dirname(__file__), "..")
_CREDS_FILE = os.path.join(_ROOT, "data", "calendar_credentials.json")
_TOKEN_FILE = os.path.join(_ROOT, "data", "gmail_token.json")

_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]

_service = None


def _disponible():
    return GMAIL_ENABLED and os.path.exists(_CREDS_FILE)


def _get_service():
    global _service
    if _service is not None:
        return _service
    if not os.path.exists(_CREDS_FILE):
        raise FileNotFoundError("Faltan credenciales en data/calendar_credentials.json.")

    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    creds = None
    if os.path.exists(_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(_TOKEN_FILE, _SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(_CREDS_FILE, _SCOPES)
            creds = flow.run_local_server(port=0)
        with open(_TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    _service = build("gmail", "v1", credentials=creds)
    return _service


def leer_correos(n=5):
    """Retorna un resumen de los últimos N correos de la bandeja de entrada."""
    if not _disponible():
        return "Gmail no está configurado."
    try:
        service  = _get_service()
        results  = service.users().messages().list(
            userId="me", labelIds=["INBOX"], maxResults=n
        ).execute()
        mensajes = results.get("messages", [])
        if not mensajes:
            return "No hay correos en la bandeja de entrada."

        resumen = []
        for ref in mensajes[:n]:
            msg = service.users().messages().get(
                userId="me", id=ref["id"],
                format="metadata",
                metadataHeaders=["From", "Subject"],
            ).execute()
            hdrs     = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
            remitente = re.sub(r"<.*?>", "", hdrs.get("From", "?")).strip()
            asunto   = hdrs.get("Subject", "(sin asunto)")
            snippet  = msg.get("snippet", "")[:80]
            resumen.append(f"De {remitente}: {asunto}. {snippet}")

        return "Últimos correos: " + " | ".join(resumen) + "."
    except Exception as ex:
        return f"No pude leer los correos: {ex}"


def enviar_correo(destinatario, asunto, cuerpo):
    """Envía un correo desde la cuenta del usuario."""
    if not _disponible():
        return "Gmail no está configurado."
    try:
        service = _get_service()
        mensaje = MIMEText(cuerpo, "plain", "utf-8")
        mensaje["to"]      = destinatario
        mensaje["subject"] = asunto
        raw = base64.urlsafe_b64encode(mensaje.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return f"Correo enviado a {destinatario}."
    except Exception as ex:
        return f"No pude enviar el correo: {ex}"
