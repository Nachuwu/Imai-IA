import os
import time
import tempfile
import numpy as np
from modules.utils import sin_acentos as _sin_acentos
import sounddevice as sd
import scipy.io.wavfile as wav
from faster_whisper import WhisperModel
from config import SAMPLE_RATE, CHUNK, SILENCIO_MAX, DURACION_MAX, UMBRAL_RMS, TEMP_WAV, GROQ_API_KEY, WAKE_WORD_MODEL, WAKE_WORD_TARGET

model      = None
umbral     = UMBRAL_RMS
_oww_model = None
_OWW_CHUNK = 1280   # 80 ms a 16 kHz
_OWW_SCORE = 0.5    # umbral de activación

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
        print(f"[ Wake word OWW: {os.path.basename(WAKE_WORD_MODEL)} ]")
    except Exception as e:
        print(f"[ openWakeWord no disponible, usando Whisper: {e} ]")


def inicializar():
    global model
    print("Cargando Whisper...")
    model = WhisperModel("small", device="cpu", compute_type="int8")
    modo = "Groq (nube)" if _groq_client else "local"
    print(f"Whisper listo. STT: {modo}")
    _cargar_oww()
    calibrar_umbral()
    print()

def calibrar_umbral():
    global umbral
    chunk_samples = int(CHUNK * SAMPLE_RATE)
    n_chunks      = int(2.0 / CHUNK)

    print("[ Calibrando micrófono... quédate en silencio ]", flush=True)
    rmss = []
    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16") as stream:
            for _ in range(n_chunks):
                chunk, _ = stream.read(chunk_samples)
                rmss.append(_rms(chunk))
    except sd.PortAudioError:
        print("[ Calibración fallida, usando umbral por defecto ]")
        return

    ruido_base = float(np.mean(rmss))
    umbral = int(np.clip(ruido_base * 2.5, 60, 350))
    print(f"[ Umbral: {umbral} (ruido ambiente: {ruido_base:.0f}) ]")

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
            print(f"[ Groq STT falló, usando local: {e} ]")

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
    print("[ En espera... di 'Imai' para activar (OWW) ]", flush=True)
    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16") as stream:
            while True:
                chunk, _ = stream.read(_OWW_CHUNK)
                audio = chunk.flatten().astype(np.float32) / 32768.0
                prediccion = _oww_model.predict(audio)
                for nombre, score in prediccion.items():
                    if score >= _OWW_SCORE:
                        print(f"[ Wake word detectado (OWW score={score:.2f}) ]", flush=True)
                        return
    except sd.PortAudioError as e:
        print(f"[ Error de micrófono: {e} ]")


def _esperar_whisper():
    """Buffer deslizante de 2s que avanza cada 0.5s — 'Imai' nunca queda cortado."""
    BUFFER_S = 2.0
    STEP_S   = 0.5
    buf_n    = int(BUFFER_S * SAMPLE_RATE)
    step_n   = int(STEP_S   * SAMPLE_RATE)
    buf      = np.zeros(buf_n, dtype=np.int16)

    print(f"[ En espera... di '{_WAKE_TARGET}' para activar ]", flush=True)
    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16") as stream:
            while True:
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
                        print(f"[ Wake word escuchó: '{texto.strip()}' ]", flush=True)
                    if _es_wake_word(texto):
                        print("[ Wake word detectado ]", flush=True)
                        return
                except Exception:
                    pass
    except sd.PortAudioError as e:
        print(f"[ Error de micrófono: {e} ]")

def escuchar():
    chunk_samples       = int(CHUNK * SAMPLE_RATE)
    chunks_silencio_max = int(SILENCIO_MAX / CHUNK)
    chunks_max          = int(DURACION_MAX / CHUNK)

    grabando        = False
    chunks_silencio = 0
    frames          = []

    print("[ Escuchando... ]", flush=True)
    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16") as stream:
            for _ in range(chunks_max):
                chunk, _ = stream.read(chunk_samples)
                energia = _rms(chunk)

                if not grabando:
                    if energia > umbral:
                        grabando = True
                        print("\a[ ● Grabando ]", flush=True)
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
        print(f"[ Error de micrófono: {e} ]")
        return "", None

    if not frames:
        print("[ Sin voz detectada ]")
        return "", None

    print("[ ■ Procesando... ]", flush=True)
    audio = np.concatenate(frames, axis=0)
    try:
        wav.write(TEMP_WAV, SAMPLE_RATE, audio)
        texto, idioma = _transcribir(TEMP_WAV)
        return texto, idioma
    except Exception as e:
        print(f"[ Error al transcribir: {e} ]")
        return "", None
