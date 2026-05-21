import json
import os
import re
from config import DATA_DIR as _DATA_DIR

_ARCHIVO   = os.path.join(_DATA_DIR, "memoria.json")
_COL_MEM   = None   # ChromaDB collection (lazy)


def cargar():
    """Retorna dict con claves 'perfil' (dict) y 'hechos' (list)."""
    try:
        with open(_ARCHIVO, encoding="utf-8") as f:
            datos = json.load(f)
        if isinstance(datos, list):
            # Migración desde formato antiguo (lista plana)
            return {"perfil": {}, "hechos": datos}
        return datos
    except (FileNotFoundError, json.JSONDecodeError):
        return {"perfil": {}, "hechos": []}


def guardar(datos):
    with open(_ARCHIVO, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)


def _get_col():
    global _COL_MEM
    if _COL_MEM is None:
        try:
            from modules.rag import _client
            _COL_MEM = _client.get_or_create_collection("memoria_imai")
        except Exception:
            pass
    return _COL_MEM

def _indexar(texto, doc_id=None):
    col = _get_col()
    if col is None:
        return
    try:
        if doc_id is None:
            doc_id = f"mem_{abs(hash(texto))}"
        existentes = set(col.get()["ids"])
        if doc_id not in existentes:
            col.add(ids=[doc_id], documents=[texto])
    except Exception:
        pass

def indexar_existentes():
    """Indexa en ChromaDB todos los hechos y perfil ya guardados en JSON."""
    datos = cargar()
    for h in datos.get("hechos", []):
        _indexar(h)
    for campo, valor in datos.get("perfil", {}).items():
        _indexar(f"{campo}: {valor}", doc_id=f"perfil_{campo}")

def buscar_semantico(query, n=5):
    """Búsqueda semántica sobre la memoria guardada."""
    col = _get_col()
    if col is None:
        return "Búsqueda vectorial no disponible."
    try:
        total = col.count()
        if total == 0:
            return "No hay nada en la memoria todavía."
        resultados = col.query(query_texts=[query], n_results=min(n, total))
        docs = resultados["documents"][0]
        if not docs:
            return "No encontré nada relevante en la memoria."
        return "Recuerdo esto: " + "; ".join(docs) + "."
    except Exception as ex:
        return f"No pude buscar en la memoria: {ex}"

def agregar(hecho):
    datos = cargar()
    if hecho not in datos["hechos"]:
        datos["hechos"].append(hecho)
        guardar(datos)
        _indexar(hecho)


def agregar_perfil(campo, valor):
    """Guarda un campo estructurado del perfil del usuario."""
    datos = cargar()
    datos["perfil"][campo.lower().strip()] = valor.strip()
    guardar(datos)
    _indexar(f"{campo}: {valor}", doc_id=f"perfil_{campo.lower().strip()}")


def actualizar(hecho_nuevo, patron=None):
    """Reemplaza un hecho existente que contenga `patron`. Si no lo encuentra, agrega."""
    datos = cargar()
    if patron:
        patron_lower = patron.lower()
        # Buscar en perfil primero
        for campo, valor in datos["perfil"].items():
            if patron_lower in campo or patron_lower in valor.lower():
                datos["perfil"][campo] = hecho_nuevo
                guardar(datos)
                return True
        # Buscar en hechos
        for i, h in enumerate(datos["hechos"]):
            if patron_lower in h.lower():
                datos["hechos"][i] = hecho_nuevo
                guardar(datos)
                return True
    if hecho_nuevo not in datos["hechos"]:
        datos["hechos"].append(hecho_nuevo)
        guardar(datos)
    return False


def como_texto():
    datos = cargar()
    perfil = datos.get("perfil", {})
    hechos = datos.get("hechos", [])
    partes = []
    if perfil:
        campos = ", ".join(f"{k}: {v}" for k, v in perfil.items())
        partes.append(f"Perfil del usuario: {campos}.")
    if hechos:
        partes.append("Otros datos del usuario:\n" + "\n".join(f"- {h}" for h in hechos))
    return "\n".join(partes)


_PAT = re.compile(
    r"\b(?:recuerda|anota|guarda|ten en cuenta|sab[eé]s que|nota que)\s+(?:que\s+)?(.+)",
    re.IGNORECASE,
)

def extraer_hecho(texto):
    m = _PAT.search(texto)
    return m.group(1).strip().rstrip(".") if m else None
