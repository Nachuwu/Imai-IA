import json
import os
import re

_ARCHIVO = os.path.join(os.path.dirname(__file__), "..", "memoria.json")

def cargar():
    try:
        with open(_ARCHIVO, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def guardar(hechos):
    with open(_ARCHIVO, "w", encoding="utf-8") as f:
        json.dump(hechos, f, ensure_ascii=False, indent=2)

def agregar(hecho):
    hechos = cargar()
    if hecho not in hechos:
        hechos.append(hecho)
        guardar(hechos)

def como_texto():
    hechos = cargar()
    if not hechos:
        return ""
    return "Lo que sé del usuario:\n" + "\n".join(f"- {h}" for h in hechos)

# Extrae el hecho de frases como "recuerda que me llamo Ignacio"
_PAT = re.compile(
    r"\b(?:recuerda|anota|guarda|ten en cuenta|sab[eé]s que|nota que)\s+(?:que\s+)?(.+)",
    re.IGNORECASE,
)

def extraer_hecho(texto):
    m = _PAT.search(texto)
    return m.group(1).strip().rstrip(".") if m else None
