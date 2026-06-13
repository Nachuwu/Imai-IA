"""
Notificaciones proactivas por Telegram (opcional).
Si TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID no están configurados, enviar() no hace nada.
"""
import logging
import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

_log = logging.getLogger(__name__)


def disponible():
    return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)


def enviar(mensaje):
    if not disponible():
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": mensaje},
            timeout=5,
        )
    except Exception as e:
        _log.warning("telegram enviar error: %s", e)
