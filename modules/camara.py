"""
Cámara en segundo plano — captura frames continuamente en un hilo daemon.
El último frame queda disponible en memoria para consultas instantáneas.
"""
import os
import logging
import threading
import time

import cv2
import numpy as np

_log = logging.getLogger(__name__)

_frame_lock  = threading.Lock()
_ultimo_frame = None   # numpy array BGR
_activa       = False
_hilo         = None
_INTERVALO    = 0.05   # segundos entre capturas (~20 fps para preview fluido)


def _bucle_camara(indice: int):
    global _ultimo_frame, _activa

    cap = cv2.VideoCapture(indice, cv2.CAP_DSHOW)
    if not cap.isOpened():
        _log.warning("Cámara %d: no se pudo abrir", indice)
        _activa = False
        return

    _log.info("Cámara %d activa en segundo plano", indice)
    while _activa:
        ok, frame = cap.read()
        if ok:
            with _frame_lock:
                _ultimo_frame = frame.copy()
        time.sleep(_INTERVALO)

    cap.release()
    _log.info("Cámara detenida")


def iniciar(indice: int = 0):
    """Arranca el hilo de captura. Llama una sola vez al inicio."""
    global _activa, _hilo
    if _activa:
        return
    _activa = True
    _hilo = threading.Thread(
        target=_bucle_camara,
        args=(indice,),
        daemon=True,
        name="camara",
    )
    _hilo.start()


def detener():
    global _activa
    _activa = False


def get_frame() -> np.ndarray | None:
    """Retorna el último frame capturado, o None si la cámara no está lista."""
    with _frame_lock:
        return _ultimo_frame.copy() if _ultimo_frame is not None else None


def guardar_frame_tmp() -> str | None:
    """Guarda el último frame como PNG temporal y retorna la ruta."""
    frame = get_frame()
    if frame is None:
        return None
    ruta = os.path.join(os.path.dirname(__file__), "..", "audio", "_camara_tmp.png")
    cv2.imwrite(ruta, frame)
    return ruta


def esta_activa() -> bool:
    return _activa and _ultimo_frame is not None
