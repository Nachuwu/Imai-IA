import os
import logging
import threading
import time
import numpy as np
from modules.utils import sin_acentos as _sin_acentos, MIC_LOCK
import sounddevice as sd
import scipy.io.wavfile as wav
from faster_whisper import WhisperModel
from config import SAMPLE_RATE, CHUNK, SILENCIO_MAX, DURACION_MAX, UMBRAL_RMS, TEMP_WAV, GROQ_API_KEY, WAKE_WORD_MODEL, WAKE_WORD_TARGET

_log = logging.getLogger(__name__)

model       = None
umbral      = UMBRAL_RMS
_oww_model  = None
nivel_audio: float = 0.0   # RMS normalizado 0.0-1.0 para el waveform de la GUI
_OWW_CHUNK = 1280   # 80 ms a 16 kHz
_OWW_SCORE = 0.5    # umbral de activación

# ---------------------------------------------------------------------------
# Stop event — permite interrumpir escuchar() y esperar_wake_word()
# ---------------------------------------------------------------------------
_stop = threading.Event()

def parar():
    _stop.set()

def limpiar_stop():
    _stop.clear()

# ---------------------------------------------------------------------------
# Modo no molestar
# ---------------------------------------------------------------------------

_no_molestar_hasta: float = 0.0

def pausar(segundos):
    global _no_molestar_hasta
    _no_molestar_hasta = time.time() + segundos

def esta_pausado():
    return time.time() < _no_molestar_hasta

# Cliente Groq (None si no hay API key o paquete no instalado)
_groq_client = None
if GROQ_API_KEY:
    try:
        from groq import Groq
        _groq_client = Groq(api_key=GROQ_API_KEY)
    except ImportError:
        pass

def _cargar_oww():
    global _oww_model
    if not os.path.exists(WAKE_WORD_MODEL):
        return
    try:
        import openwakeword
        openwakeword.utils.download_models()  # descarga melspectrogram.onnx y otros base si faltan
        from openwakeword.model import Model as OWWModel
        _oww_model = OWWModel(wakeword_models=[WAKE_WORD_MODEL], inference_framework="onnx")
        _log.info("Wake word OWW: %s", os.path.basename(WAKE_WORD_MODEL))
    except Exception as e:
        _log.warning("openWakeWord no disponible, usando Whisper: %s", e)


def inicializar():
    global model
    _log.info("Cargando Whisper...")
    model = WhisperModel("small", device="cpu", compute_type="int8")
    modo = "Groq (nube)" if _groq_client else "local"
    _log.info("Whisper listo. STT: %s", modo)
    _cargar_oww()
    calibrar_umbral()

def calibrar_umbral():
    global umbral
    chunk_samples = int(CHUNK * SAMPLE_RATE)
    n_chunks      = int(2.0 / CHUNK)

    _log.info("Calibrando micrófono... quédate en silencio")
    rmss = []
    try:
        with MIC_LOCK, sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16") as stream:
            for _ in range(n_chunks):
                chunk, _ = stream.read(chunk_samples)
                rmss.append(_rms(chunk))
    except sd.PortAudioError:
        _log.warning("Calibración fallida, usando umbral por defecto")
        return

    ruido_base = float(np.mean(rmss))
    umbral = int(np.clip(ruido_base * 2.5, 60, 350))
    _log.info("Umbral: %d (ruido ambiente: %.0f)", umbral, ruido_base)

def _rms(chunk):
    return np.sqrt(np.mean(chunk.astype(np.float32) ** 2))

def _transcribir(archivo):
    """Retorna (texto, 'es') — siempre en español."""
    if _groq_client:
        try:
            with open(archivo, "rb") as f:
                resultado = _groq_client.audio.transcriptions.create(
                    file=(os.path.basename(archivo), f.read()),
                    model="whisper-large-v3",
                    response_format="text",
                    language="es",
                )
            return resultado.strip(), "es"
        except Exception as e:
            _log.warning("Groq STT falló, usando local: %s", e)

    segs, _ = model.transcribe(archivo, language="es")
    return " ".join(s.text for s in segs).strip(), "es"

_WAKE_TARGET = WAKE_WORD_TARGET
_WAKE_FUZZY_THRESHOLD = 82  # similitud mínima (0-100) para considerar match

def _es_wake_word(texto):
    """Devuelve True si el texto contiene la wake word o algo muy similar."""
    from rapidfuzz.distance import Levenshtein
    texto = _sin_acentos(texto.lower().strip())
    if _WAKE_TARGET in texto:
        return True
    target_len = len(_WAKE_TARGET)
    for palabra in texto.split():
        palabra = palabra.strip(".,;:!?¿¡")
        if not palabra:
            continue
        # Ignorar palabras que sean menos del 85% de la longitud del target
        # Evita que "escucha" (7) active "escuchame" (9)
        if len(palabra) < target_len * 0.85:
            continue
        max_len = max(len(palabra), target_len)
        dist    = Levenshtein.distance(palabra, _WAKE_TARGET)
        sim     = (1 - dist / max_len) * 100
        if sim >= _WAKE_FUZZY_THRESHOLD:
            return True
    return False

def esperar_wake_word():
    """Escucha en bucle hasta detectar 'imai'. Usa OWW si el modelo está cargado, Whisper si no."""
    if _oww_model is not None:
        _esperar_oww()
    else:
        _esperar_whisper()


def _esperar_oww():
    _log.info("En espera... di 'Imai' para activar (OWW)")
    try:
        with MIC_LOCK, sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16") as stream:
            while not _stop.is_set():
                chunk, _ = stream.read(_OWW_CHUNK)
                audio = chunk.flatten().astype(np.float32) / 32768.0
                prediccion = _oww_model.predict(audio)
                for nombre, score in prediccion.items():
                    if score >= _OWW_SCORE:
                        _log.info("Wake word detectado (OWW score=%.2f)", score)
                        return
    except sd.PortAudioError as e:
        _log.error("Error de micrófono: %s", e)


def _esperar_whisper():
    """Buffer deslizante de 2s que avanza cada 0.5s — 'Imai' nunca queda cortado."""
    BUFFER_S = 2.0
    STEP_S   = 0.5
    buf_n    = int(BUFFER_S * SAMPLE_RATE)
    step_n   = int(STEP_S   * SAMPLE_RATE)
    buf      = np.zeros(buf_n, dtype=np.int16)

    _log.info("En espera... di '%s' para activar", _WAKE_TARGET)
    try:
        with MIC_LOCK, sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16") as stream:
            while not _stop.is_set():
                chunk, _ = stream.read(step_n)
                chunk = chunk.flatten()
                buf   = np.roll(buf, -step_n)
                buf[-step_n:] = chunk

                if _rms(chunk.reshape(-1, 1)) < umbral:
                    continue

                audio_f32 = buf.astype(np.float32) / 32768.0
                try:
                    segs, _ = model.transcribe(
                        audio_f32, language="es",
                        vad_filter=True, beam_size=3,
                        condition_on_previous_text=False,
                        temperature=0.0,
                    )
                    texto = " ".join(s.text for s in segs)
                    if texto.strip():
                        _log.debug("Wake word escuchó: '%s'", texto.strip())
                    if _es_wake_word(texto):
                        _log.info("Wake word detectado")
                        return
                except Exception:
                    pass
    except sd.PortAudioError as e:
        _log.error("Error de micrófono: %s", e)

def escuchar():
    chunk_samples       = int(CHUNK * SAMPLE_RATE)
    chunks_silencio_max = int(SILENCIO_MAX / CHUNK)
    chunks_max          = int(DURACION_MAX / CHUNK)

    grabando        = False
    chunks_silencio = 0
    frames          = []

    global nivel_audio
    print("[ Escuchando... ]", flush=True)
    try:
        with MIC_LOCK, sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16") as stream:
            for _ in range(chunks_max):
                if _stop.is_set():
                    break
                chunk, _ = stream.read(chunk_samples)
                energia = _rms(chunk)
                nivel_audio = min(1.0, float(energia) / max(umbral * 2, 1))

                if not grabando:
                    if energia > umbral:
                        grabando = True
                        _log.info("Grabando")
                        frames.append(chunk)
                else:
                    frames.append(chunk)
                    if energia < umbral:
                        chunks_silencio += 1
                        if chunks_silencio >= chunks_silencio_max:
                            break
                    else:
                        chunks_silencio = 0
    except sd.PortAudioError as e:
        _log.error("Error de micrófono: %s", e)
        return "", None

    nivel_audio = 0.0
    if not frames:
        _log.info("Sin voz detectada")
        return "", None

    _log.info("Procesando...")
    audio = np.concatenate(frames, axis=0)
    try:
        wav.write(TEMP_WAV, SAMPLE_RATE, audio)
        texto, idioma = _transcribir(TEMP_WAV)
        return texto, idioma
    except Exception as e:
        _log.error("Error al transcribir: %s", e)
        return "", None
