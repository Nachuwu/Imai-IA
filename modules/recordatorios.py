"""
Recordatorios con fecha/hora usando APScheduler.
Los recordatorios persisten en recordatorios.json y se restauran al iniciar.
"""
import json
import os
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

_scheduler = None
_hablar_fn = None
from config import DATA_DIR as _DATA_DIR
_ARCHIVO = os.path.join(_DATA_DIR, "recordatorios.json")


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
    if _hablar_fn:
        _hablar_fn(f"Recordatorio: {mensaje}")


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
