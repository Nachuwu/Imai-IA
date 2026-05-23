"""
Alertas proactivas sin que el usuario pregunte:
- Resumen diario a las 22:00
- Clima adverso (lluvia, tormenta)
- Correos nuevos importantes
- Inactividad prolongada (>45 min)
"""
import glob
import json
import os
import time
from datetime import datetime

from config import DATA_DIR, CIUDAD, GMAIL_ENABLED

_hablar_fn    = None
_get_turno_fn = None   # callable → float timestamp del último turno del usuario
_ESTADO_FILE  = os.path.join(DATA_DIR, "proactivo_estado.json")

_WMO_LLUVIA = {51, 53, 55, 61, 63, 65, 71, 73, 75, 80, 81, 82, 95, 96, 99}
_WMO_DESC   = {
    51: "llovizna leve",  53: "llovizna",       55: "llovizna fuerte",
    61: "lluvia leve",    63: "lluvia",          65: "lluvia fuerte",
    71: "nieve leve",     73: "nieve",           75: "nieve fuerte",
    80: "chubascos",      81: "chubascos fuertes", 82: "chubascos muy fuertes",
    95: "tormenta",       96: "tormenta con granizo", 99: "tormenta fuerte",
}

_INACTIVIDAD_MIN = 45

# ──────────────────────────────────────────────────────────────────────────────
# Estado persistente
# ──────────────────────────────────────────────────────────────────────────────

def _cargar():
    try:
        with open(_ESTADO_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _guardar(estado):
    try:
        with open(_ESTADO_FILE, "w", encoding="utf-8") as f:
            json.dump(estado, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# ──────────────────────────────────────────────────────────────────────────────
# Resumen diario — 22:00
# ──────────────────────────────────────────────────────────────────────────────

def _resumen_diario():
    import modules.tools as t
    import modules.recordatorios as rec

    partes = ["Resumen del día."]

    try:
        partes.append(t.get_clima(CIUDAD))
    except Exception:
        pass

    try:
        import modules.calendario as cal
        eventos = cal.ver_eventos_hoy()
        if "No tienes eventos" not in eventos and "no está configurado" not in eventos:
            partes.append(eventos)
    except Exception:
        pass

    try:
        recs = rec.listar()
        if "No tienes" not in recs and "No hay" not in recs:
            partes.append(recs)
    except Exception:
        pass

    try:
        hoy      = datetime.now().strftime("%Y-%m-%d")
        hist_dir = os.path.join(os.path.dirname(__file__), "..", "historial")
        archivos = glob.glob(os.path.join(hist_dir, f"{hoy}.jsonl"))
        if archivos:
            with open(archivos[0], encoding="utf-8") as f:
                n = sum(1 for _ in f)
            partes.append(f"Tuvimos {n} interacciones hoy.")
    except Exception:
        pass

    if _hablar_fn:
        _hablar_fn(" ".join(partes))

# ──────────────────────────────────────────────────────────────────────────────
# Clima — cada hora
# ──────────────────────────────────────────────────────────────────────────────

def _check_clima():
    import requests
    try:
        geo = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": CIUDAD, "count": 1, "language": "es"},
            timeout=5,
        ).json()
        if not geo.get("results"):
            return
        r    = geo["results"][0]
        data = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": r["latitude"], "longitude": r["longitude"],
                "current": "temperature_2m,weathercode",
                "timezone": "auto",
            },
            timeout=5,
        ).json()
        codigo = data["current"]["weathercode"]
        temp   = round(data["current"]["temperature_2m"])

        estado      = _cargar()
        era_adverso = estado.get("clima_era_adverso", False)

        if codigo in _WMO_LLUVIA and not era_adverso:
            desc = _WMO_DESC.get(codigo, "condiciones adversas")
            estado.update({"clima_codigo_anterior": codigo, "clima_era_adverso": True})
            _guardar(estado)
            if _hablar_fn:
                _hablar_fn(f"Aviso de clima: {desc} en {CIUDAD}, {temp} grados.")
        elif codigo not in _WMO_LLUVIA and era_adverso:
            estado.update({"clima_codigo_anterior": codigo, "clima_era_adverso": False})
            _guardar(estado)
    except Exception:
        pass

# ──────────────────────────────────────────────────────────────────────────────
# Correos importantes — cada 15 min
# ──────────────────────────────────────────────────────────────────────────────

def _check_correos():
    if not GMAIL_ENABLED:
        return
    try:
        import modules.gmail as gm
        correos = gm.get_correos_raw(n=5)
        if not correos:
            return

        estado      = _cargar()
        notificados = set(estado.get("correos_notificados", []))
        nuevos      = [c for c in correos if c["id"] not in notificados]
        if not nuevos:
            return

        for c in nuevos:
            notificados.add(c["id"])
        estado["correos_notificados"] = list(notificados)[-200:]
        _guardar(estado)

        from modules.claude_llm import _get_client
        from config import CLAUDE_MODEL
        client  = _get_client()
        resumen = "\n".join(f"De: {c['de']} | Asunto: {c['asunto']}" for c in nuevos)
        resp    = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=80,
            messages=[{"role": "user", "content":
                f"¿Hay algún correo urgente o importante aquí? "
                f"Si SÍ: responde 'SÍ: [una frase]'. Si NO: responde solo 'NO'.\n\n{resumen}"
            }],
        )
        texto = resp.content[0].text.strip()
        if texto.upper().startswith("SÍ") or texto.upper().startswith("SI"):
            mensaje = texto.split(":", 1)[-1].strip() if ":" in texto else texto
            if _hablar_fn:
                _hablar_fn(f"Tienes un correo importante: {mensaje}")
    except Exception as e:
        print(f"[ proactivo correos error: {e} ]")

# ──────────────────────────────────────────────────────────────────────────────
# Inactividad — cada 5 min
# ──────────────────────────────────────────────────────────────────────────────

def _check_inactividad():
    if _get_turno_fn is None:
        return
    ahora  = time.time()
    ultimo = _get_turno_fn()
    if ultimo is None or (ahora - ultimo) < _INACTIVIDAD_MIN * 60:
        return

    estado        = _cargar()
    ultima_alerta = estado.get("inactividad_ultima_alerta", 0)
    if (ahora - ultima_alerta) < _INACTIVIDAD_MIN * 60:
        return

    estado["inactividad_ultima_alerta"] = ahora
    _guardar(estado)

    minutos = int((ahora - ultimo) / 60)
    if _hablar_fn:
        _hablar_fn(f"Llevas {minutos} minutos sin interactuar. Considera levantarte, tomar agua o estirar.")

# ──────────────────────────────────────────────────────────────────────────────
# Inicialización
# ──────────────────────────────────────────────────────────────────────────────

def inicializar(hablar_cb, scheduler, get_turno_fn):
    global _hablar_fn, _get_turno_fn
    _hablar_fn    = hablar_cb
    _get_turno_fn = get_turno_fn

    scheduler.add_job(_resumen_diario,   "cron",     hour=22, minute=0, id="proact_resumen",      replace_existing=True)
    scheduler.add_job(_check_clima,      "interval", minutes=60,        id="proact_clima",         replace_existing=True)
    scheduler.add_job(_check_correos,    "interval", minutes=15,        id="proact_correos",       replace_existing=True)
    scheduler.add_job(_check_inactividad,"interval", minutes=5,         id="proact_inactividad",   replace_existing=True)

    print("[ Proactivo: resumen 22:00 · clima/hora · correos/15min · inactividad/5min ]")
