"""
Respaldo diario de los archivos de datos críticos del usuario.
Copia data/*.json relevantes a data/backups/YYYY-MM-DD/ y elimina respaldos antiguos.
"""
import os
import shutil
from datetime import datetime, timedelta
from config import DATA_DIR

_ARCHIVOS = [
    "memoria.json",
    "proyectos.json",
    "recordatorios.json",
    "historial_sesion.json",
    "historial_recordatorios.json",
    "patrones_estado.json",
]

_DIAS_RETENCION = 14


def respaldar():
    hoy     = datetime.now().strftime("%Y-%m-%d")
    destino = os.path.join(DATA_DIR, "backups", hoy)
    os.makedirs(destino, exist_ok=True)

    for nombre in _ARCHIVOS:
        origen = os.path.join(DATA_DIR, nombre)
        if os.path.exists(origen):
            shutil.copy2(origen, os.path.join(destino, nombre))

    _limpiar_antiguos()


def _limpiar_antiguos():
    base = os.path.join(DATA_DIR, "backups")
    if not os.path.isdir(base):
        return
    limite = datetime.now() - timedelta(days=_DIAS_RETENCION)
    for carpeta in os.listdir(base):
        ruta = os.path.join(base, carpeta)
        try:
            fecha = datetime.strptime(carpeta, "%Y-%m-%d")
        except ValueError:
            continue
        if fecha < limite and os.path.isdir(ruta):
            shutil.rmtree(ruta, ignore_errors=True)
