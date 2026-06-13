"""
Recordatorios con fecha/hora usando APScheduler.
Los recordatorios persisten en recordatorios.json y se restauran al iniciar.
"""
import json
import os
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from rapidfuzz import fuzz
import modules.telegram as tg

_scheduler = None
_hablar_fn = None
from config import DATA_DIR as _DATA_DIR
_ARCHIVO          = os.path.join(_DATA_DIR, "recordatorios.json")
_HISTORIAL_ARCHIVO = os.path.join(_DATA_DIR, "historial_recordatorios.json")
_PATRONES_ARCHIVO  = os.path.join(_DATA_DIR, "patrones_estado.json")
_MAX_HISTORIAL     = 200


def get_scheduler():
    return _scheduler


def inicializar(hablar_cb):
    global _scheduler, _hablar_fn
    _hablar_fn = hablar_cb
    _scheduler = BackgroundScheduler(timezone="America/Santiago")
    _scheduler.start()
    _restaurar()


def crear(mensaje, cuando_str):
    """cuando_str: 'YYYY-MM-DD HH:MM'"""
    try:
        cuando = datetime.strptime(cuando_str.strip(), "%Y-%m-%d %H:%M")
    except ValueError:
        return "No entendí la fecha. Necesito el formato YYYY-MM-DD HH:MM."

    if cuando <= datetime.now():
        return "Esa fecha ya pasó."

    job_id = f"rec_{int(cuando.timestamp())}"
    _scheduler.add_job(
        _disparar, "date",
        run_date=cuando,
        args=[mensaje, job_id],
        id=job_id,
        replace_existing=True,
    )
    _guardar(job_id, mensaje, cuando_str)
    _log_historial(mensaje, cuando)

    cuando_fmt = cuando.strftime("%d/%m a las %H:%M")
    return f"Listo, te recuerdo el {cuando_fmt}: {mensaje}."


_FRECUENCIA_MAP = {
    "diario":          "*",
    "entre_semana":    "mon-fri",
    "fines_de_semana": "sat,sun",
    "lunes":    "mon", "martes":   "tue", "miercoles": "wed",
    "jueves":   "thu", "viernes":  "fri", "sabado":    "sat",
    "domingo":  "sun",
}

def crear_recurrente(mensaje, hora_str, frecuencia):
    """
    Crea una alarma recurrente.
    hora_str: 'HH:MM'
    frecuencia: 'diario', 'lunes', 'entre_semana', 'fines_de_semana', etc.
    """
    try:
        hora, minuto = [int(x) for x in hora_str.strip().split(":")]
    except ValueError:
        return "No entendí la hora. Necesito el formato HH:MM."

    dia_cron = _FRECUENCIA_MAP.get(frecuencia.lower().strip(), "*")
    job_id   = f"rec_cron_{frecuencia}_{hora:02d}{minuto:02d}"

    _scheduler.add_job(
        _disparar, "cron",
        hour=hora, minute=minuto,
        day_of_week=dia_cron if dia_cron != "*" else None,
        args=[mensaje, job_id],
        id=job_id,
        replace_existing=True,
    )
    _guardar(job_id, mensaje, hora_str, frecuencia=frecuencia)

    freq_txt = {"diario": "todos los días", "entre_semana": "de lunes a viernes",
                "fines_de_semana": "los fines de semana"}.get(
        frecuencia.lower(), f"cada {frecuencia}")
    return f"Alarma creada: {freq_txt} a las {hora_str}, mensaje: {mensaje}."


def cancelar_ultimo():
    jobs = _scheduler.get_jobs()
    if not jobs:
        return "No hay recordatorios pendientes."
    job = jobs[-1]
    _eliminar_guardado(job.id)
    _scheduler.remove_job(job.id)
    return "Último recordatorio cancelado."


def listar():
    jobs = _scheduler.get_jobs()
    if not jobs:
        return "No tienes recordatorios pendientes."
    datos  = _cargar_json()
    partes = []
    for job in jobs:
        msg    = job.args[0] if job.args else "?"
        info   = datos.get(job.id, {})
        if "frecuencia" in info:
            freq_txt = {"diario": "todos los días", "entre_semana": "lun–vie",
                        "fines_de_semana": "sáb–dom"}.get(
                info["frecuencia"], f"cada {info['frecuencia']}")
            partes.append(f"{msg} ({freq_txt} a las {info['cuando']})")
        elif job.next_run_time:
            cuando = job.next_run_time.strftime("%d/%m a las %H:%M")
            partes.append(f"{msg} el {cuando}")
    return "Tus recordatorios: " + "; ".join(partes) + "." if partes else "No hay recordatorios activos."


# ---------------------------------------------------------------------------
# Persistencia
# ---------------------------------------------------------------------------

def _disparar(mensaje, job_id):
    _eliminar_guardado(job_id)
    texto = f"Recordatorio: {mensaje}"
    if _hablar_fn:
        _hablar_fn(texto)
    tg.enviar(texto)


def _guardar(job_id, mensaje, cuando_str, frecuencia=None):
    datos = _cargar_json()
    entrada = {"mensaje": mensaje, "cuando": cuando_str}
    if frecuencia:
        entrada["frecuencia"] = frecuencia
    datos[job_id] = entrada
    with open(_ARCHIVO, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)


def _eliminar_guardado(job_id):
    datos = _cargar_json()
    if job_id in datos:
        datos.pop(job_id)
        with open(_ARCHIVO, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)


def _cargar_json():
    if os.path.exists(_ARCHIVO):
        try:
            with open(_ARCHIVO, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _restaurar():
    datos  = _cargar_json()
    ahora  = datetime.now()
    viejos = []
    for job_id, info in datos.items():
        try:
            if "frecuencia" in info:
                # Alarma recurrente
                hora, minuto = [int(x) for x in info["cuando"].split(":")]
                dia_cron = _FRECUENCIA_MAP.get(info["frecuencia"].lower(), "*")
                _scheduler.add_job(
                    _disparar, "cron",
                    hour=hora, minute=minuto,
                    day_of_week=dia_cron if dia_cron != "*" else None,
                    args=[info["mensaje"], job_id],
                    id=job_id,
                    replace_existing=True,
                )
            else:
                # Recordatorio puntual
                cuando = datetime.strptime(info["cuando"], "%Y-%m-%d %H:%M")
                if cuando > ahora:
                    _scheduler.add_job(
                        _disparar, "date",
                        run_date=cuando,
                        args=[info["mensaje"], job_id],
                        id=job_id,
                        replace_existing=True,
                    )
                else:
                    viejos.append(job_id)
        except Exception:
            viejos.append(job_id)

    if viejos:
        for job_id in viejos:
            datos.pop(job_id, None)
        with open(_ARCHIVO, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Historial de recordatorios puntuales (para detectar patrones de rutina)
# ---------------------------------------------------------------------------

def _cargar_historial():
    if os.path.exists(_HISTORIAL_ARCHIVO):
        try:
            with open(_HISTORIAL_ARCHIVO, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _log_historial(mensaje, cuando):
    historial = _cargar_historial()
    historial.append({
        "mensaje": mensaje,
        "dia_semana": cuando.weekday(),
        "hora": cuando.strftime("%H:%M"),
    })
    historial = historial[-_MAX_HISTORIAL:]
    with open(_HISTORIAL_ARCHIVO, "w", encoding="utf-8") as f:
        json.dump(historial, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Detección de patrones de rutina
# ---------------------------------------------------------------------------

_DIAS_SEMANA = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]


def _cargar_patrones_estado():
    if os.path.exists(_PATRONES_ARCHIVO):
        try:
            with open(_PATRONES_ARCHIVO, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"sugeridos": []}


def marcar_sugerido(clave):
    estado = _cargar_patrones_estado()
    if clave not in estado["sugeridos"]:
        estado["sugeridos"].append(clave)
        with open(_PATRONES_ARCHIVO, "w", encoding="utf-8") as f:
            json.dump(estado, f, ensure_ascii=False, indent=2)


def _ya_es_recurrente(mensaje, dia_semana):
    """Revisa si ya existe una alarma recurrente que cubra este mensaje y día."""
    dia_nombre = _DIAS_SEMANA[dia_semana]
    for info in _cargar_json().values():
        frecuencia = info.get("frecuencia")
        if not frecuencia:
            continue
        cubre_dia = (
            frecuencia == "diario"
            or (frecuencia == "entre_semana" and dia_semana <= 4)
            or (frecuencia == "fines_de_semana" and dia_semana >= 5)
            or frecuencia == dia_nombre
        )
        if cubre_dia and fuzz.ratio(mensaje.lower(), info["mensaje"].lower()) >= 75:
            return True
    return False


def detectar_patrones(min_ocurrencias=3):
    """
    Busca recordatorios puntuales repetidos el mismo día de la semana y hora similar.
    Retorna una lista de candidatos aún no sugeridos ni cubiertos por una alarma existente.
    """
    historial = _cargar_historial()
    if len(historial) < min_ocurrencias:
        return []

    grupos = []
    for entrada in historial:
        hora_h   = entrada["hora"].split(":")[0]
        agregado = False
        for g in grupos:
            if (g["dia_semana"] == entrada["dia_semana"]
                    and g["hora"].split(":")[0] == hora_h
                    and fuzz.ratio(g["mensajes"][0].lower(), entrada["mensaje"].lower()) >= 75):
                g["mensajes"].append(entrada["mensaje"])
                agregado = True
                break
        if not agregado:
            grupos.append({
                "mensajes": [entrada["mensaje"]],
                "dia_semana": entrada["dia_semana"],
                "hora": entrada["hora"],
            })

    estado     = _cargar_patrones_estado()
    sugeridos  = set(estado["sugeridos"])
    candidatos = []
    for g in grupos:
        if len(g["mensajes"]) < min_ocurrencias:
            continue
        mensaje = max(set(g["mensajes"]), key=g["mensajes"].count)
        clave   = f"{mensaje.lower()}_{g['dia_semana']}_{g['hora']}"
        if clave in sugeridos:
            continue
        if _ya_es_recurrente(mensaje, g["dia_semana"]):
            continue
        candidatos.append({"mensaje": mensaje, "dia_semana": g["dia_semana"], "hora": g["hora"], "clave": clave})

    return candidatos
