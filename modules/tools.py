import os
import re
import ast
import glob
import json
import logging
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

_log = logging.getLogger(__name__)

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
# Búsqueda web (DuckDuckGo → Wikipedia — sin API key)
# ---------------------------------------------------------------------------

def _buscar_wikipedia(query):
    """Fallback: busca en Wikipedia en español y devuelve el primer párrafo."""
    try:
        r = requests.get(
            "https://es.wikipedia.org/api/rest_v1/page/summary/" + requests.utils.quote(query),
            timeout=5,
            headers={"User-Agent": "Imai-IA/1.0"},
        )
        if r.status_code == 200:
            data = r.json()
            extracto = data.get("extract", "")
            if extracto:
                return extracto[:500]
        # Si no hay artículo exacto, buscar por texto
        r2 = requests.get(
            "https://es.wikipedia.org/w/api.php",
            params={
                "action": "query", "list": "search", "srsearch": query,
                "format": "json", "srlimit": 1, "utf8": 1,
            },
            timeout=5,
        )
        resultados = r2.json().get("query", {}).get("search", [])
        if resultados:
            titulo = resultados[0]["title"]
            r3 = requests.get(
                "https://es.wikipedia.org/api/rest_v1/page/summary/" + requests.utils.quote(titulo),
                timeout=5,
                headers={"User-Agent": "Imai-IA/1.0"},
            )
            if r3.status_code == 200:
                return r3.json().get("extract", "")[:500]
    except Exception:
        pass
    return ""

def buscar_web(query):
    # 1. DuckDuckGo Instant Answer
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
        temas = data.get("RelatedTopics", [])
        if temas and isinstance(temas[0], dict):
            texto = temas[0].get("Text", "")
            if texto:
                return texto[:400]
    except Exception as e:
        _log.warning("buscar_web DDG error: %s", e)

    # 2. Wikipedia en español
    wiki = _buscar_wikipedia(query)
    if wiki:
        return wiki

    return f"No encontré información sobre '{query}'."

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
        _log.error("captura_pantalla error: %s", e)
        return "No pude tomar la captura de pantalla."

def analizar_pantalla(pregunta="¿Qué hay en esta pantalla?"):
    import tempfile
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            ruta = f.name
        ImageGrab.grab().save(ruta)
    except Exception as e:
        _log.error("analizar_pantalla captura error: %s", e)
        return "No pude tomar la captura de pantalla."
    try:
        from modules.claude_llm import analizar_imagen
        return analizar_imagen(ruta, pregunta)
    except Exception as e:
        _log.error("analizar_pantalla error: %s", e)
        return "No pude analizar la pantalla."
    finally:
        try:
            os.unlink(ruta)
        except Exception:
            pass

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
        _log.error("controlar_ventana error: %s", e)
        return "No pude controlar esa ventana."

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
    anterior = pyperclip.paste()
    pyperclip.copy(texto)
    _pag.hotkey("ctrl", "v")
    time.sleep(0.15)
    pyperclip.copy(anterior)
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

def ver_camara(pregunta="¿Cómo está la persona frente a la cámara?"):
    """Analiza al usuario usando el último frame de la cámara."""
    import modules.camara as _cam
    from modules.claude_llm import analizar_imagen
    ruta = _cam.guardar_frame_tmp()
    if ruta is None:
        return "La cámara no está lista todavía."
    try:
        return analizar_imagen(ruta, pregunta + " Enfócate en la persona: expresión, postura, estado de ánimo, ropa.")
    except Exception as ex:
        _log.error("ver_camara error: %s", ex)
        return "No pude analizar la imagen de la cámara."

def describir_entorno(pregunta="¿Qué hay en el entorno?"):
    """Analiza el entorno usando el último frame de la cámara."""
    import modules.camara as _cam
    from modules.claude_llm import analizar_imagen
    ruta = _cam.guardar_frame_tmp()
    if ruta is None:
        return "La cámara no está lista todavía."
    try:
        return analizar_imagen(ruta, pregunta + " Enfócate en el entorno: objetos, habitación, fondo, iluminación.")
    except Exception as ex:
        _log.error("describir_entorno error: %s", ex)
        return "No pude analizar el entorno."

def click_en_texto(texto):
    """
    Usa Ctrl+F para resaltar el texto en pantalla, toma screenshot con el
    resaltado activo y manda a Vision para localizar con mayor precisión.
    """
    import tempfile, time as _t2
    from modules.claude_llm import analizar_imagen

    # Resaltar el texto con Ctrl+F (el navegador/app lo destaca en amarillo)
    _pag.hotkey("ctrl", "f")
    _t2.sleep(0.35)
    _pag.hotkey("ctrl", "a")          # limpiar búsqueda anterior
    _pag.typewrite(texto[:40], interval=0.04)
    _t2.sleep(0.5)

    # Screenshot CON el texto resaltado visible
    img = ImageGrab.grab()
    w_img, h_img = img.size
    w_pag, h_pag = _pag.size()
    sx = w_pag / w_img
    sy = h_pag / h_img

    # Cerrar barra de búsqueda
    _pag.press("escape")
    _t2.sleep(0.1)

    # Redimensionar a 1280px max ancho — Vision es más preciso con imágenes estándar
    if w_img > 1280:
        factor = 1280 / w_img
        img = img.resize((1280, int(h_img * factor)))
    else:
        factor = 1.0
    w_vis, h_vis = img.size

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        img.save(f.name)
        ruta = f.name
    try:
        pregunta = (
            f"Captura de pantalla de {w_vis}x{h_vis} píxeles. "
            f"Busca el texto '{texto}' — está resaltado en amarillo/naranja por una búsqueda activa. "
            f"Da las coordenadas X,Y del centro de ese elemento resaltado. "
            f"Formato: '542,387' (solo dos números, coma, sin espacios). "
            f"Si no lo ves: 'no encontrado'."
        )
        respuesta = analizar_imagen(ruta, pregunta).strip().lower()
    finally:
        os.unlink(ruta)

    if "no encontrado" in respuesta or ("no" in respuesta and "," not in respuesta):
        return f"No encontré '{texto}' en pantalla."
    m = re.search(r"(\d+)\s*,\s*(\d+)", respuesta)
    if not m:
        return f"No pude interpretar la posición de '{texto}'."

    # Revertir resize y aplicar escala DPI
    x = int(int(m.group(1)) / factor * sx)
    y = int(int(m.group(2)) / factor * sy)
    _log.debug("click_en_texto: → (%d,%d) factor=%.2f escala=%.2f,%.2f", x, y, factor, sx, sy)
    _pag.click(x, y)
    return f"Hice clic en '{texto}'."

# ---------------------------------------------------------------------------
# Leer artículos y páginas web
# ---------------------------------------------------------------------------

def leer_url(url=None, pregunta=None):
    """Descarga una URL, extrae el texto y devuelve un resumen o responde una pregunta."""
    import time as _time
    if not url:
        try:
            import pygetwindow as gw
            win = gw.getActiveWindow()
            _NAVEGADORES = ("chrome", "edge", "firefox", "opera", "brave", "safari")
            if win and any(n in win.title.lower() for n in _NAVEGADORES):
                _pag.hotkey("ctrl", "l")
                _time.sleep(0.35)
                _pag.hotkey("ctrl", "a")
                _time.sleep(0.1)
                _pag.hotkey("ctrl", "c")
                _time.sleep(0.3)
                url = pyperclip.paste().strip()
        except Exception:
            pass

    if not url or not url.startswith("http"):
        return "No encontré una URL. Dime qué página quieres leer."

    try:
        from bs4 import BeautifulSoup
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        contenido = soup.get_text(separator=" ", strip=True)[:3000]
    except Exception as e:
        _log.error("leer_url error: %s", e)
        return "No pude acceder a esa página web."

    if not contenido:
        return "No pude extraer texto de esa página."

    try:
        from modules.claude_llm import _get_client
        from config import CLAUDE_MODEL
        client = _get_client()
        if pregunta:
            prompt_texto = f"Basándote en este texto, responde en 2 oraciones en español, sin markdown: {pregunta}\n\nTexto:\n{contenido}"
        else:
            prompt_texto = f"Resume este texto en 2 oraciones en español, sin markdown:\n\n{contenido}"
        r = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt_texto}],
        )
        return r.content[0].text.strip()
    except Exception:
        return contenido[:300] + "..."
