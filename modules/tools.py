import os
import re
import ast
import glob
import json
import operator
import threading
import time
import requests
import pyperclip
import comtypes
from datetime import datetime
from PIL import ImageGrab
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

# ---------------------------------------------------------------------------
# Volumen
# ---------------------------------------------------------------------------

# Interfaz cacheada — se crea una sola vez en el hilo principal para evitar
# que el GC intente destruirla desde otro hilo (causa errores de VTable en COM).
_vol = None

def _get_vol():
    global _vol
    if _vol is None:
        comtypes.CoInitialize()
        devices = AudioUtilities.GetSpeakers()
        dev = getattr(devices, "_dev", devices)
        iface = dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        _vol = cast(iface, POINTER(IAudioEndpointVolume))
    return _vol

def set_volumen(pct):
    _get_vol().SetMasterVolumeLevelScalar(max(0.0, min(1.0, pct / 100)), None)
    return f"Volumen al {pct} por ciento"

def get_volumen():
    pct = round(_get_vol().GetMasterVolumeLevelScalar() * 100)
    return f"El volumen está al {pct} por ciento"

def subir_volumen(delta=10):
    vol = _get_vol()
    actual = round(vol.GetMasterVolumeLevelScalar() * 100)
    nuevo = min(100, actual + delta)
    vol.SetMasterVolumeLevelScalar(nuevo / 100, None)
    return f"Volumen al {nuevo} por ciento"

def bajar_volumen(delta=10):
    vol = _get_vol()
    actual = round(vol.GetMasterVolumeLevelScalar() * 100)
    nuevo = max(0, actual - delta)
    vol.SetMasterVolumeLevelScalar(nuevo / 100, None)
    return f"Volumen al {nuevo} por ciento"

def silenciar():
    _get_vol().SetMute(1, None)
    return "Silenciado"

def activar_sonido():
    _get_vol().SetMute(0, None)
    return "Sonido activado"

# ---------------------------------------------------------------------------
# Timers
# ---------------------------------------------------------------------------

_timers = {}  # nombre -> Thread, para poder cancelarlos si hace falta

def crear_timer(segundos, callback, nombre=None):
    nombre = nombre or f"timer_{int(time.time())}"
    cancelado = threading.Event()

    def _run():
        cancelado.wait(timeout=segundos)
        _timers.pop(nombre, None)
        if not cancelado.is_set():
            callback(f"Timer listo: han pasado {_fmt_tiempo(segundos)}.")

    t = threading.Thread(target=_run, daemon=True, name=nombre)
    _timers[nombre] = (t, cancelado)
    t.start()

    return f"Timer de {_fmt_tiempo(segundos)} iniciado."

def cancelar_timer(nombre=None):
    if nombre and nombre in _timers:
        _, cancelado = _timers.pop(nombre)
        cancelado.set()
        return f"Timer '{nombre}' cancelado."
    if _timers:
        nombre, (_, cancelado) = next(reversed(_timers.items()))
        _timers.pop(nombre)
        cancelado.set()
        return "Último timer cancelado."
    return "No hay timers activos."

def _fmt_tiempo(segundos):
    if segundos < 60:
        return f"{segundos} segundos"
    if segundos < 3600:
        m, s = divmod(segundos, 60)
        return f"{m} minuto{'s' if m != 1 else ''}" + (f" y {s} segundos" if s else "")
    h, resto = divmod(segundos, 3600)
    m = resto // 60
    return f"{h} hora{'s' if h != 1 else ''}" + (f" y {m} minutos" if m else "")

# ---------------------------------------------------------------------------
# Búsqueda de archivos
# ---------------------------------------------------------------------------

# Carpetas prioritarias antes de ir al home completo
_CARPETAS_PRIORITARIAS = [
    os.path.expanduser(r"~\Desktop"),
    os.path.expanduser(r"~\Documents"),
    os.path.expanduser(r"~\Downloads"),
    os.path.expanduser(r"~\Music"),
    os.path.expanduser(r"~\Videos"),
    os.path.expanduser(r"~\Pictures"),
]

def buscar_archivos(nombre, carpeta=None, callback=None):
    """Busca archivos. Si se pasa callback, corre en segundo plano y lo llama al terminar."""
    def _buscar():
        resultados = []
        if carpeta:
            patron = os.path.join(carpeta, "**", f"*{nombre}*")
            resultados = glob.glob(patron, recursive=True)[:5]
        else:
            for base in _CARPETAS_PRIORITARIAS:
                if not os.path.isdir(base):
                    continue
                patron = os.path.join(base, "**", f"*{nombre}*")
                resultados += glob.glob(patron, recursive=True)
                if len(resultados) >= 5:
                    break
            resultados = resultados[:5]

        if resultados:
            resultado = "Encontré: " + ", ".join(os.path.basename(r) for r in resultados)
        else:
            resultado = f"No encontré archivos con el nombre '{nombre}'."

        if callback:
            callback(resultado)
        return resultado

    if callback:
        threading.Thread(target=_buscar, daemon=True).start()
        return None
    return _buscar()

def abrir_archivo(ruta):
    if os.path.exists(ruta):
        os.startfile(ruta)
        return f"Abriendo {os.path.basename(ruta)}"
    return f"No existe el archivo: {ruta}"

# ---------------------------------------------------------------------------
# Hora y fecha
# ---------------------------------------------------------------------------

_DIAS  = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
          "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

def get_hora():
    now = datetime.now()
    h, m = now.hour, now.minute
    if m == 0:   return f"Son las {h} en punto."
    if m == 15:  return f"Son las {h} y cuarto."
    if m == 30:  return f"Son las {h} y media."
    if m == 45:  return f"Son las {(h % 12) + 1} menos cuarto."
    return f"Son las {h} y {m} minutos."

def get_fecha():
    now = datetime.now()
    return (f"Hoy es {_DIAS[now.weekday()]} {now.day} "
            f"de {_MESES[now.month - 1]} de {now.year}.")

# ---------------------------------------------------------------------------
# Clima (Open-Meteo, gratis, sin API key)
# ---------------------------------------------------------------------------

_WMO = {
    0: "cielo despejado", 1: "mayormente despejado",
    2: "parcialmente nublado", 3: "nublado",
    45: "neblina", 48: "neblina con escarcha",
    51: "llovizna leve", 53: "llovizna", 55: "llovizna fuerte",
    61: "lluvia leve", 63: "lluvia", 65: "lluvia fuerte",
    71: "nieve leve", 73: "nieve", 75: "nieve fuerte",
    80: "chubascos", 81: "chubascos fuertes", 82: "chubascos muy fuertes",
    95: "tormenta", 96: "tormenta con granizo", 99: "tormenta fuerte",
}

def get_clima(ciudad="Santiago"):
    try:
        geo = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": ciudad, "count": 1, "language": "es"},
            timeout=5,
        ).json()
        if not geo.get("results"):
            return f"No encontré la ciudad {ciudad}."
        r = geo["results"][0]
        weather = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": r["latitude"], "longitude": r["longitude"],
                "current": "temperature_2m,weathercode,windspeed_10m",
                "timezone": "auto",
            },
            timeout=5,
        ).json()
        c = weather["current"]
        desc = _WMO.get(c["weathercode"], "condiciones variadas")
        return (f"En {r['name']}: {round(c['temperature_2m'])}°C, {desc}, "
                f"viento a {round(c['windspeed_10m'])} km/h.")
    except Exception:
        return "No pude obtener el clima ahora mismo."

# ---------------------------------------------------------------------------
# Calculadora (eval seguro con ast)
# ---------------------------------------------------------------------------

_OPS_BIN = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.Pow: operator.pow, ast.Mod: operator.mod,
}
_OPS_UN = {ast.USub: operator.neg, ast.UAdd: operator.pos}

def _eval_safe(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS_BIN:
        return _OPS_BIN[type(node.op)](_eval_safe(node.left), _eval_safe(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS_UN:
        return _OPS_UN[type(node.op)](_eval_safe(node.operand))
    raise ValueError("Operación no permitida")

def calcular(expresion):
    exp = expresion.lower().strip()
    exp = re.sub(r'(\d+(?:\.\d+)?)\s*%\s*de\s*(\d+(?:\.\d+)?)', r'(\1/100)*\2', exp)
    exp = exp.replace("más", "+").replace("mas", "+")
    exp = exp.replace("menos", "-")
    exp = re.sub(r'\bpor\b', "*", exp)
    exp = re.sub(r'\bentre\b|\bdividido\b', "/", exp)
    exp = re.sub(r'\belevado a\b|\ba la\b', "**", exp)
    exp = exp.replace("%", "/100").replace(",", ".")
    exp = re.sub(r'[^0-9+\-*/().\s]', '', exp).strip()
    if not exp:
        return None
    try:
        resultado = _eval_safe(ast.parse(exp, mode="eval").body)
        if isinstance(resultado, float):
            return str(int(resultado)) if resultado.is_integer() else f"{resultado:.4f}".rstrip('0').rstrip('.')
        return str(resultado)
    except Exception:
        return None

# ---------------------------------------------------------------------------
# Portapapeles
# ---------------------------------------------------------------------------

def get_portapapeles():
    try:
        texto = pyperclip.paste().strip()
        if not texto:
            return "El portapapeles está vacío."
        recortado = texto[:300] + ("..." if len(texto) > 300 else "")
        return f"Tienes copiado: {recortado}"
    except Exception:
        return "No pude acceder al portapapeles."

# ---------------------------------------------------------------------------
# Búsqueda web (DuckDuckGo Instant Answer — sin API key)
# ---------------------------------------------------------------------------

def buscar_web(query):
    try:
        r = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
            timeout=6,
        )
        data = r.json()
        respuesta = data.get("AbstractText") or data.get("Answer") or ""
        if respuesta:
            return respuesta[:600]
        # Intentar con los RelatedTopics
        temas = data.get("RelatedTopics", [])
        if temas and isinstance(temas[0], dict):
            texto = temas[0].get("Text", "")
            if texto:
                return texto[:400]
        return f"No encontré información directa sobre {query}."
    except Exception as e:
        return f"No pude buscar ahora mismo: {e}"

# ---------------------------------------------------------------------------
# Captura de pantalla
# ---------------------------------------------------------------------------

def _captura_ruta():
    """Toma captura y devuelve la ruta del archivo."""
    carpeta = os.path.expanduser(r"~\Pictures\Imai")
    os.makedirs(carpeta, exist_ok=True)
    nombre = datetime.now().strftime("captura_%Y%m%d_%H%M%S.png")
    ruta = os.path.join(carpeta, nombre)
    ImageGrab.grab().save(ruta)
    return ruta

def captura_pantalla():
    try:
        ruta = _captura_ruta()
        return f"Captura guardada como {os.path.basename(ruta)}."
    except Exception as e:
        return f"No pude tomar la captura: {e}"

def analizar_pantalla(pregunta="¿Qué hay en esta pantalla?"):
    try:
        ruta = _captura_ruta()
    except Exception as e:
        return f"No pude tomar la captura: {e}"
    try:
        from modules.claude_llm import analizar_imagen
        return analizar_imagen(ruta, pregunta)
    except Exception as e:
        return f"No pude analizar la pantalla: {e}"

# ---------------------------------------------------------------------------
# Notificaciones de escritorio
# ---------------------------------------------------------------------------

def notificar(titulo, mensaje):
    try:
        from plyer import notification
        notification.notify(title=titulo, message=mensaje, app_name="Imai", timeout=8)
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Spotify (teclas multimedia, sin API key)
# ---------------------------------------------------------------------------

import ctypes as _ctypes
import subprocess as _sp

_VK_MEDIA = {"play_pause": 0xB3, "siguiente": 0xB0, "anterior": 0xB1, "parar": 0xB2}

def _tecla_media(accion):
    vk = _VK_MEDIA.get(accion)
    if vk:
        _ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
        _ctypes.windll.user32.keybd_event(vk, 0, 2, 0)

def spotify_play_pause():
    _tecla_media("play_pause")
    return "Play pausa."

def spotify_siguiente():
    _tecla_media("siguiente")
    return "Siguiente canción."

def spotify_anterior():
    _tecla_media("anterior")
    return "Canción anterior."

def spotify_parar():
    _tecla_media("parar")
    return "Música detenida."

_SPOTIFY_HIST_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "spotify_historial.json")

def _log_cancion(titulo):
    try:
        historial = []
        if os.path.exists(_SPOTIFY_HIST_FILE):
            with open(_SPOTIFY_HIST_FILE, encoding="utf-8") as f:
                historial = json.load(f)
        if not historial or historial[-1].get("titulo") != titulo:
            historial.append({"titulo": titulo, "fecha": datetime.now().isoformat()})
            historial = historial[-200:]  # máximo 200 entradas
            with open(_SPOTIFY_HIST_FILE, "w", encoding="utf-8") as f:
                json.dump(historial, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def get_cancion_spotify():
    try:
        r = _sp.run(
            ["powershell", "-NoProfile", "-Command",
             'Get-Process -Name "Spotify" -EA SilentlyContinue | '
             'Where-Object {$_.MainWindowTitle -ne ""} | '
             'Select-Object -Expand MainWindowTitle -First 1'],
            capture_output=True, text=True, timeout=3,
        )
        titulo = r.stdout.strip()
        if titulo and titulo.lower() != "spotify":
            _log_cancion(titulo)
            return f"Está sonando: {titulo}."
        return "Spotify está pausado o no hay nada sonando."
    except Exception:
        return "No pude leer la canción actual."

def historial_spotify(n=10):
    """Retorna las últimas N canciones escuchadas."""
    try:
        if not os.path.exists(_SPOTIFY_HIST_FILE):
            return "Todavía no hay historial de Spotify."
        with open(_SPOTIFY_HIST_FILE, encoding="utf-8") as f:
            historial = json.load(f)
        if not historial:
            return "Todavía no hay historial de Spotify."
        recientes = historial[-n:][::-1]
        partes = [e["titulo"] for e in recientes]
        return "Canciones recientes: " + "; ".join(partes) + "."
    except Exception:
        return "No pude leer el historial de Spotify."

# ---------------------------------------------------------------------------
# Control de ventanas
# ---------------------------------------------------------------------------

def controlar_ventana(accion, titulo=None):
    import pygetwindow as gw
    from rapidfuzz import process as fz

    if accion == "listar":
        titulos = [w.title for w in gw.getAllWindows() if w.title.strip()]
        return ("Ventanas abiertas: " + ", ".join(titulos[:10]) + ".") if titulos else "No hay ventanas abiertas."

    if not titulo:
        return "¿Qué ventana quieres controlar?"

    ventanas = gw.getWindowsWithTitle(titulo)
    if not ventanas:
        todas = [w.title for w in gw.getAllWindows() if w.title.strip()]
        match = fz.extractOne(titulo, todas, score_cutoff=60)
        if match:
            ventanas = gw.getWindowsWithTitle(match[0])

    if not ventanas:
        return f"No encontré una ventana con '{titulo}'."

    win    = ventanas[0]
    nombre = win.title[:50]

    try:
        if accion == "minimizar":
            win.minimize();  return f"Minimicé '{nombre}'."
        if accion == "maximizar":
            win.maximize();  return f"Maximicé '{nombre}'."
        if accion == "restaurar":
            win.restore();   return f"Restauré '{nombre}'."
        if accion == "enfocar":
            win.activate();  return f"Cambié a '{nombre}'."
    except Exception as e:
        return f"No pude controlar la ventana: {e}"

    return f"Acción '{accion}' no reconocida."

# ---------------------------------------------------------------------------
# Control del PC
# ---------------------------------------------------------------------------

def apagar_pc():
    import subprocess
    subprocess.run(["shutdown", "/s", "/t", "10"])
    return "Apagando el PC en 10 segundos. Di 'cancela apagado' si cambias de idea."

def reiniciar_pc():
    import subprocess
    subprocess.run(["shutdown", "/r", "/t", "10"])
    return "Reiniciando el PC en 10 segundos."

def cancelar_apagado():
    import subprocess
    subprocess.run(["shutdown", "/a"])
    return "Apagado cancelado."

def bloquear_pantalla():
    import ctypes
    ctypes.windll.user32.LockWorkStation()
    return "Pantalla bloqueada."

def suspender_pc():
    import subprocess
    subprocess.Popen(["rundll32", "powrprof.dll,SetSuspendState", "0", "1", "0"])
    return "Entrando en suspensión."

# ---------------------------------------------------------------------------
# Brillo de pantalla
# ---------------------------------------------------------------------------

def get_brillo():
    try:
        import screen_brightness_control as sbc
        return f"El brillo está al {sbc.get_brightness()[0]} por ciento."
    except Exception:
        return "No pude leer el brillo."

def set_brillo(pct):
    try:
        import screen_brightness_control as sbc
        sbc.set_brightness(max(0, min(100, pct)))
        return f"Brillo al {pct} por ciento."
    except Exception:
        return "No pude cambiar el brillo."

def subir_brillo(delta=10):
    try:
        import screen_brightness_control as sbc
        nuevo = min(100, sbc.get_brightness()[0] + delta)
        sbc.set_brightness(nuevo)
        return f"Brillo al {nuevo} por ciento."
    except Exception:
        return "No pude cambiar el brillo."

def bajar_brillo(delta=10):
    try:
        import screen_brightness_control as sbc
        nuevo = max(0, sbc.get_brightness()[0] - delta)
        sbc.set_brightness(nuevo)
        return f"Brillo al {nuevo} por ciento."
    except Exception:
        return "No pude cambiar el brillo."

# ---------------------------------------------------------------------------
# Control de mouse y teclado (pyautogui)
# ---------------------------------------------------------------------------

import pyautogui as _pag
_pag.FAILSAFE = True   # mover mouse a esquina superior izquierda aborta
_pag.PAUSE    = 0.05

def escribir_teclado(texto):
    """Escribe texto usando el portapapeles (soporta unicode)."""
    pyperclip.copy(texto)
    _pag.hotkey("ctrl", "v")
    return f"Escribí: {texto[:60]}{'...' if len(texto) > 60 else ''}."

def presionar_tecla(combo):
    """Presiona una tecla o combinación: 'enter', 'ctrl+c', 'alt+f4', etc."""
    partes = [t.strip() for t in combo.lower().split("+")]
    if len(partes) == 1:
        _pag.press(partes[0])
    else:
        _pag.hotkey(*partes)
    return f"Tecla: {combo}."

def scroll_pantalla(direccion="abajo", cantidad=3):
    clicks = cantidad if direccion == "arriba" else -cantidad
    _pag.scroll(clicks)
    return f"Scroll {'arriba' if clicks > 0 else 'abajo'}."

def click_en(x, y):
    _pag.click(x, y)
    return f"Clic en ({x}, {y})."

def click_en_texto(texto):
    """Toma captura, usa Claude Vision para encontrar el elemento y hace clic."""
    import tempfile
    from modules.claude_llm import analizar_imagen
    img = ImageGrab.grab()
    w, h = img.size
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        img.save(f.name)
        ruta = f.name
    try:
        pregunta = (
            f"Busca el elemento de interfaz con el texto o ícono '{texto}' "
            f"en esta pantalla de {w}x{h} píxeles. "
            f"Responde ÚNICAMENTE con las coordenadas del centro en formato 'x,y'. "
            f"Si no lo encuentras, responde 'no encontrado'."
        )
        respuesta = analizar_imagen(ruta, pregunta).strip().lower()
    finally:
        os.unlink(ruta)

    if "no encontrado" in respuesta or "no" in respuesta and "," not in respuesta:
        return f"No encontré '{texto}' en pantalla."
    m = re.search(r"(\d+)\s*,\s*(\d+)", respuesta)
    if not m:
        return f"No pude interpretar la posición de '{texto}'."
    x, y = int(m.group(1)), int(m.group(2))
    _pag.click(x, y)
    return f"Hice clic en '{texto}'."
