import json
import os
from datetime import datetime

_ARCHIVO = os.path.join(os.path.dirname(__file__), "..", "historial.json")

def registrar(texto, intent, respuesta):
    entrada = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "texto":     texto,
        "intent":    intent,
        "respuesta": respuesta,
    }
    try:
        try:
            with open(_ARCHIVO, "r", encoding="utf-8") as f:
                datos = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            datos = []
        datos.append(entrada)
        with open(_ARCHIVO, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
