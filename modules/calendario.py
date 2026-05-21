"""
Google Calendar — ver eventos del día y crear citas por voz.
Requiere: google-api-python-client, google-auth-oauthlib

Configuración inicial:
1. Crea un proyecto en https://console.cloud.google.com
2. Habilita la Google Calendar API
3. Crea credenciales OAuth 2.0 (tipo: app de escritorio)
4. Descarga el JSON y guárdalo como data/calendar_credentials.json
5. La primera vez que se llame, se abrirá el navegador para autorizar acceso
   y se guardará el token en data/calendar_token.json
"""
import os
import datetime
from config import GOOGLE_CALENDAR_ENABLED

_ROOT      = os.path.join(os.path.dirname(__file__), "..")
_CREDS_FILE = os.path.join(_ROOT, "data", "calendar_credentials.json")
_TOKEN_FILE = os.path.join(_ROOT, "data", "calendar_token.json")

_SCOPES = ["https://www.googleapis.com/auth/calendar"]

_service = None


def _get_service():
    global _service
    if _service is not None:
        return _service

    if not os.path.exists(_CREDS_FILE):
        raise FileNotFoundError(
            f"Faltan credenciales de Google Calendar en {_CREDS_FILE}. "
            "Lee modules/calendario.py para instrucciones de configuración."
        )

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

    _service = build("calendar", "v3", credentials=creds)
    return _service


def _disponible():
    return GOOGLE_CALENDAR_ENABLED and os.path.exists(_CREDS_FILE)


def ver_eventos_hoy():
    """Devuelve un string con los eventos de hoy en el calendario."""
    if not _disponible():
        return "El calendario no está configurado."
    try:
        service = _get_service()
        tz_local = datetime.datetime.now().astimezone().tzinfo
        hoy    = datetime.datetime.now(tz_local).date()
        inicio = datetime.datetime(hoy.year, hoy.month, hoy.day,  0,  0,  0, tzinfo=tz_local).isoformat()
        fin    = datetime.datetime(hoy.year, hoy.month, hoy.day, 23, 59, 59, tzinfo=tz_local).isoformat()

        resultado = service.events().list(
            calendarId="primary",
            timeMin=inicio,
            timeMax=fin,
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        eventos = resultado.get("items", [])
        if not eventos:
            return "No tienes eventos hoy."

        partes = []
        for e in eventos:
            inicio_e = e["start"].get("dateTime", e["start"].get("date", ""))
            hora = ""
            if "T" in inicio_e:
                hora = inicio_e[11:16] + " — "
            partes.append(f"{hora}{e.get('summary', 'Sin título')}")

        return "Hoy tienes: " + "; ".join(partes) + "."
    except Exception as ex:
        return f"No pude obtener el calendario: {ex}"


def crear_evento(titulo, cuando, duracion_min=60):
    """
    Crea un evento en el calendario.
    cuando: string ISO 'YYYY-MM-DD HH:MM' (fecha y hora local)
    duracion_min: duración en minutos (default 60)
    """
    if not _disponible():
        return "El calendario no está configurado."
    try:
        service = _get_service()

        dt_inicio = datetime.datetime.strptime(cuando, "%Y-%m-%d %H:%M")
        dt_fin    = dt_inicio + datetime.timedelta(minutes=duracion_min)

        evento = {
            "summary": titulo,
            "start":   {"dateTime": dt_inicio.isoformat(), "timeZone": "America/Santiago"},
            "end":     {"dateTime": dt_fin.isoformat(),    "timeZone": "America/Santiago"},
        }

        service.events().insert(calendarId="primary", body=evento).execute()
        hora_str = dt_inicio.strftime("%H:%M")
        return f"Evento '{titulo}' creado para las {hora_str}."
    except ValueError:
        return "Formato de fecha inválido. Usa YYYY-MM-DD HH:MM."
    except Exception as ex:
        return f"No pude crear el evento: {ex}"
