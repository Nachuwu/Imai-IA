import json
import os
from datetime import datetime

_CARPETA = os.path.join(os.path.dirname(__file__), "..", "historial")

def guardar(messages, intent=None, objeto=None, herramienta=False):
    try:
        os.makedirs(_CARPETA, exist_ok=True)
        hoy = datetime.now().strftime("%Y-%m-%d")
        archivo = os.path.join(_CARPETA, f"{hoy}.jsonl")
        entrada = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "messages":  messages,
            "intent":    intent,
            "objeto":    str(objeto) if objeto is not None else None,
            "herramienta": herramienta,
        }
        with open(archivo, "a", encoding="utf-8") as f:
            f.write(json.dumps(entrada, ensure_ascii=False) + "\n")
    except Exception:
        pass
