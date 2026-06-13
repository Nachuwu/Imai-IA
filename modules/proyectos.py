"""
Hilo de proyectos: rastrea en qué proyectos está trabajando el usuario,
su estado y la última acción realizada. Persiste en data/proyectos.json.
"""
import json
import os
from datetime import datetime
from rapidfuzz import process as fuzz
from config import DATA_DIR as _DATA_DIR

_ARCHIVO = os.path.join(_DATA_DIR, "proyectos.json")
_COL_PROY = None   # ChromaDB collection (lazy)


def cargar():
    try:
        with open(_ARCHIVO, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def guardar(datos):
    with open(_ARCHIVO, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)


def _get_col():
    global _COL_PROY
    if _COL_PROY is None:
        try:
            from modules.rag import _client
            _COL_PROY = _client.get_or_create_collection("memoria_imai")
        except Exception:
            pass
    return _COL_PROY


def _doc_id(nombre):
    return f"proyecto_{nombre.lower().strip().replace(' ', '_')}"


def _texto_proyecto(p):
    texto = f"Proyecto {p['nombre']}: estado {p['estado']}"
    if p.get("ultima_accion"):
        texto += f", última acción: {p['ultima_accion']}"
    if p.get("notas"):
        texto += f", notas: {p['notas']}"
    return texto


def _indexar(p):
    col = _get_col()
    if col is None:
        return
    try:
        col.upsert(ids=[_doc_id(p["nombre"])], documents=[_texto_proyecto(p)])
    except Exception:
        pass


def _desindexar(nombre):
    col = _get_col()
    if col is None:
        return
    try:
        col.delete(ids=[_doc_id(nombre)])
    except Exception:
        pass


def indexar_existentes():
    """Indexa en ChromaDB todos los proyectos ya guardados en JSON."""
    for p in cargar():
        _indexar(p)


def _buscar(nombre, datos):
    """Busca un proyecto por nombre exacto o aproximado. Retorna su índice o None."""
    nombre_l = nombre.lower().strip()
    for i, p in enumerate(datos):
        if p["nombre"].lower() == nombre_l:
            return i
    if not datos:
        return None
    nombres = [p["nombre"] for p in datos]
    match = fuzz.extractOne(nombre, nombres, score_cutoff=60)
    if match is None:
        return None
    return next(i for i, p in enumerate(datos) if p["nombre"] == match[0])


def crear(nombre, estado=None, notas=None):
    datos = cargar()
    if _buscar(nombre, datos) is not None:
        return f"Ya tengo un proyecto llamado {nombre}. Usa actualizar si quieres cambiar algo."
    proyecto = {
        "nombre": nombre,
        "estado": estado or "en curso",
        "ultima_accion": "",
        "notas": notas or "",
        "actualizado": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    datos.append(proyecto)
    guardar(datos)
    _indexar(proyecto)
    return f"Proyecto {nombre} agregado, estado: {proyecto['estado']}."


def actualizar(nombre, estado=None, ultima_accion=None, notas=None):
    datos = cargar()
    idx = _buscar(nombre, datos)
    if idx is None:
        return crear(nombre, estado, notas)
    p = datos[idx]
    if estado:
        p["estado"] = estado
    if ultima_accion:
        p["ultima_accion"] = ultima_accion
    if notas:
        p["notas"] = notas
    p["actualizado"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    guardar(datos)
    _indexar(p)
    return f"Proyecto {p['nombre']} actualizado."


def eliminar(nombre):
    datos = cargar()
    idx = _buscar(nombre, datos)
    if idx is None:
        return f"No encontré un proyecto llamado {nombre}."
    nombre_real = datos.pop(idx)["nombre"]
    guardar(datos)
    _desindexar(nombre_real)
    return f"Proyecto {nombre_real} eliminado del seguimiento."


def listar():
    datos = cargar()
    if not datos:
        return "No tienes proyectos registrados."
    partes = []
    for p in datos:
        txt = f"{p['nombre']} ({p['estado']})"
        if p.get("ultima_accion"):
            txt += f", última acción: {p['ultima_accion']}"
        partes.append(txt)
    return "Tus proyectos: " + "; ".join(partes) + "."


def como_texto():
    datos = cargar()
    if not datos:
        return ""
    partes = ["Proyectos en curso del usuario:"]
    for p in datos:
        linea = f"- {p['nombre']}: estado = {p['estado']}"
        if p.get("ultima_accion"):
            linea += f", última acción: {p['ultima_accion']}"
        if p.get("notas"):
            linea += f", notas: {p['notas']}"
        linea += f" (actualizado {p['actualizado']})"
        partes.append(linea)
    return "\n".join(partes)
