import json
import os
import tempfile
import threading
import unicodedata

# Serializa el acceso al micrófono entre el loop principal (stt.py) y el
# monitor de palabras de interrupción durante el TTS (tts.py), para evitar
# que dos sd.InputStream se abran al mismo tiempo.
MIC_LOCK = threading.Lock()


def sin_acentos(texto):
    return unicodedata.normalize("NFD", texto).encode("ascii", "ignore").decode()


def guardar_json(ruta, datos):
    """Escribe JSON de forma atómica: escribe a un temporal y reemplaza el archivo final."""
    directorio = os.path.dirname(ruta) or "."
    fd, tmp = tempfile.mkstemp(dir=directorio, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        os.replace(tmp, ruta)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
