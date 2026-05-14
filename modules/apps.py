import os
import glob
import json
import subprocess
import threading
import time
from rapidfuzz import process as fuzz

_CARPETAS_LNK = [
    os.path.expanduser(r"~\AppData\Roaming\Microsoft\Windows\Start Menu\Programs"),
    r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs",
    os.path.expanduser(r"~\Desktop"),
]

_CARPETAS_EXE = [
    r"C:\Program Files",
    r"C:\Program Files (x86)",
]

_CACHE_FILE = os.path.join(os.path.dirname(__file__), "..", "apps_cache.json")
_CACHE_TTL  = 86400  # 24 horas

_indice     = {}
_exe_indice = {}
_escaneado  = threading.Event()

# ---------------------------------------------------------------------------
# Caché
# ---------------------------------------------------------------------------

def _mtime_carpetas():
    """Retorna el mtime más reciente entre todas las carpetas LNK."""
    mtime = 0.0
    for c in _CARPETAS_LNK:
        if os.path.isdir(c):
            mtime = max(mtime, os.path.getmtime(c))
    return mtime

def _cache_valido():
    if not os.path.exists(_CACHE_FILE):
        return False
    try:
        with open(_CACHE_FILE, "r", encoding="utf-8") as f:
            datos = json.load(f)
        ts = datos.get("timestamp", 0)
        if time.time() - ts > _CACHE_TTL:
            return False
        if _mtime_carpetas() > ts:
            return False
        return True
    except Exception:
        return False

def _cargar_cache():
    with open(_CACHE_FILE, "r", encoding="utf-8") as f:
        datos = json.load(f)
    return datos["indice"], datos["exe_indice"]

def _guardar_cache(indice, exe_indice):
    try:
        with open(_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": time.time(),
                "indice":     indice,
                "exe_indice": exe_indice,
            }, f, ensure_ascii=False)
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Escaneo
# ---------------------------------------------------------------------------

def escanear_en_segundo_plano():
    threading.Thread(target=_escanear, daemon=True, name="app-scanner").start()

def _escanear():
    global _indice, _exe_indice

    if _cache_valido():
        try:
            _indice, _exe_indice = _cargar_cache()
            _escaneado.set()
            print(f"[ {len(_indice)} apps cargadas desde caché ]")
            return
        except Exception:
            pass

    tmp_abrir = {}
    tmp_exe   = {}

    for carpeta in _CARPETAS_LNK:
        if not os.path.isdir(carpeta):
            continue
        for ruta in glob.glob(os.path.join(carpeta, "**", "*.lnk"), recursive=True):
            nombre = os.path.splitext(os.path.basename(ruta))[0].lower()
            tmp_abrir[nombre] = ruta

    for base in _CARPETAS_EXE:
        if not os.path.isdir(base):
            continue
        try:
            for entrada in os.scandir(base):
                if not entrada.is_dir(follow_symlinks=False):
                    continue
                try:
                    for archivo in os.scandir(entrada.path):
                        if archivo.is_file() and archivo.name.lower().endswith(".exe"):
                            nombre = os.path.splitext(archivo.name)[0].lower()
                            tmp_abrir.setdefault(nombre, archivo.path)
                            tmp_exe[nombre] = archivo.name
                except PermissionError:
                    pass
        except PermissionError:
            pass

    _indice     = tmp_abrir
    _exe_indice = tmp_exe
    _escaneado.set()
    _guardar_cache(tmp_abrir, tmp_exe)
    print(f"[ {len(_indice)} apps indexadas y guardadas en caché ]")

# ---------------------------------------------------------------------------
# Búsqueda y acciones
# ---------------------------------------------------------------------------

def _buscar_abrir(nombre):
    if not _escaneado.is_set():
        _escaneado.wait(timeout=30)
    match = fuzz.extractOne(nombre.lower(), _indice.keys(), score_cutoff=60)
    if match:
        key = match[0]
        return _indice[key], key
    return None, None

def _buscar_exe(nombre):
    if not _escaneado.is_set():
        _escaneado.wait(timeout=30)
    match = fuzz.extractOne(nombre.lower(), _exe_indice.keys(), score_cutoff=60)
    if match:
        return _exe_indice[match[0]]
    return None

def abrir(nombre):
    ruta, key = _buscar_abrir(nombre)
    if ruta:
        os.startfile(ruta)
        return key
    return None

def cerrar(nombre):
    exe = _buscar_exe(nombre)
    if exe:
        subprocess.call(
            ["taskkill", "/f", "/im", exe],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return os.path.splitext(exe)[0]

    _, key = _buscar_abrir(nombre)
    if key:
        subprocess.call(
            ["taskkill", "/f", "/im", f"{key}.exe"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return key
    return None
