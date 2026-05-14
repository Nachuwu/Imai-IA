import os
import time
import tempfile
import numpy as np
from modules.utils import sin_acentos as _sin_acentos
import sounddevice as sd
import scipy.io.wavfile as wav
from faster_whisper import WhisperModel
from config import SAMPLE_RATE, CHUNK, SILENCIO_MAX, DURACION_MAX, UMBRAL_RMS, TEMP_WAV, GROQ_API_KEY

model  = None
umbral = UMBRAL_RMS

# ---------------------------------------------------------------------------
# Modo no molestar
# ---------------------------------------------------------------------------

_no_molestar_hasta: float = 0.0

def pausar(segundos):
    global _no_molestar_hasta
    _no_molestar_hasta = time.time() + segundos

def esta_pausado():
    return time.time() < _no_molestar_hasta

def reanudar():
    global _no_molestar_hasta
    _no_molestar_hasta = 0.0

# Cliente Groq (None si no hay API key o paquete no instalado)
_groq_client = None
if GROQ_API_KEY:
    try:
        from groq import Groq
        _groq_client = Groq(api_key=GROQ_API_KEY)
    except ImportError:
        pass

def inicializar():
    global model
    print("Cargando Whisper...")
    model = WhisperModel("small", device="cpu", compute_type="int8")
    modo = "Groq (nube)" if _groq_client else "local"
    print(f"Whisper listo. STT: {modo}")
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
    umbral = int(np.clip(ruido_base * 4, 80, 600))
    print(f"[ Umbral: {umbral} (ruido ambiente: {ruido_base:.0f}) ]")

def _rms(chunk):
    return np.sqrt(np.mean(chunk.astype(np.float32) ** 2))

def _transcribir(archivo):
    if _groq_client:
        try:
            with open(archivo, "rb") as f:
                resultado = _groq_client.audio.transcriptions.create(
                    file=(os.path.basename(archivo), f.read()),
                    model="whisper-large-v3-turbo",
                    language="es",
                    response_format="text",
                )
            return resultado.strip()
        except Exception as e:
            print(f"[ Groq STT falló, usando local: {e} ]")

    # fallback: faster-whisper local
    segs, _ = model.transcribe(archivo, language="es")
    return " ".join(s.text for s in segs).strip()

# Variantes que Whisper puede producir al escuchar "Imai"
_WAKE_VARIANTS = {"imai", "imay", "imal", "imax", "emai", "amai", "y mai", "i mai", "y may"}

def esperar_wake_word():
    """Escucha en bucle hasta detectar 'imai' o variantes. Bloquea hasta activación."""
    chunk_samples = int(1.5 * SAMPLE_RATE)
    print("[ En espera... di 'Imai' para activar ]", flush=True)
    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16") as stream:
            while True:
                chunk, _ = stream.read(chunk_samples)
                if _rms(chunk) < umbral:
                    continue

                fd, tmp = tempfile.mkstemp(suffix=".wav")
                os.close(fd)
                try:
                    wav.write(tmp, SAMPLE_RATE, chunk)
                    segs, _ = model.transcribe(
                        tmp, language="es",
                        vad_filter=False, beam_size=1,
                        condition_on_previous_text=False,
                    )
                    texto = _sin_acentos(" ".join(s.text for s in segs).lower().strip())
                    if any(v in texto for v in _WAKE_VARIANTS):
                        return
                except Exception:
                    pass
                finally:
                    try:
                        os.unlink(tmp)
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
        return ""

    if not frames:
        print("[ Sin voz detectada ]")
        return ""

    print("[ ■ Procesando... ]", flush=True)
    audio = np.concatenate(frames, axis=0)
    try:
        wav.write(TEMP_WAV, SAMPLE_RATE, audio)
        return _transcribir(TEMP_WAV)
    except Exception as e:
        print(f"[ Error al transcribir: {e} ]")
        return ""
