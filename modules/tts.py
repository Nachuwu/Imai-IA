import asyncio
import sys
import time
import logging
import warnings
import subprocess
import shutil
import threading
import unicodedata
import numpy as np
import sounddevice as sd
import edge_tts
from config import VOZ, AUDIO_FILE, PIPER_MODEL

_log = logging.getLogger(__name__)


def _sin_acentos(texto):
    return unicodedata.normalize("NFD", texto).encode("ascii", "ignore").decode("utf-8")

# Suprimir warnings de sesiones aiohttp no cerradas al interrumpir
logging.getLogger("asyncio").setLevel(logging.ERROR)
logging.getLogger("aiohttp").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", message="Unclosed client session")
warnings.filterwarnings("ignore", message="Task was destroyed but it is pending")

_evento_interrupcion = threading.Event()
_KEYWORDS = {"detente", "para", "espera", "basta", "alto", "stop"}

def fue_interrumpido():
    return _evento_interrupcion.is_set()

def parar():
    """Interrumpe la reproducción TTS en curso (llamado al hacer Detener)."""
    _evento_interrupcion.set()

def hablar(texto):
    _evento_interrupcion.clear()
    evento_fin = threading.Event()

    hilo_monitor = threading.Thread(
        target=_monitor_keywords,
        args=(evento_fin,),
        daemon=True
    )
    hilo_monitor.start()

    if PIPER_MODEL:
        _hablar_piper(texto)
    elif shutil.which("ffplay"):
        try:
            asyncio.run(_streaming(texto))
        except Exception as e:
            _log.warning("TTS streaming falló, usando fallback: %s", e)
            _hablar_archivo(texto)
    else:
        _hablar_archivo(texto)

    evento_fin.set()

_piper_voice = None

def _get_piper_voice():
    global _piper_voice
    if _piper_voice is None:
        from piper.voice import PiperVoice
        _piper_voice = PiperVoice.load(PIPER_MODEL)
    return _piper_voice

def _hablar_piper(texto):
    try:
        voice  = _get_piper_voice()
        chunks = list(voice.synthesize(texto))
        if not chunks:
            raise RuntimeError("Piper no generó audio")
        sample_rate = chunks[0].sample_rate
        audio = np.concatenate([c.audio_int16_array for c in chunks])
        arr   = audio.astype(np.float32) / 32768.0
        sd.play(arr, samplerate=sample_rate)
        stream = sd.get_stream()
        while stream is not None and stream.active:
            if _evento_interrupcion.is_set():
                sd.stop()
                return
            time.sleep(0.05)
    except Exception as e:
        _log.warning("Piper falló: %s", e)
        _hablar_archivo(texto)

def _hablar_archivo(texto):
    try:
        generar(texto)
        reproducir()
    except Exception as e:
        _log.error("Error en TTS: %s", e)
        _hablar_local(texto)

def _hablar_local(texto):
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty("rate", 165)
        engine.say(texto)
        engine.runAndWait()
    except Exception:
        print(f"Imai: {texto}")

async def _streaming(texto):
    communicate = edge_tts.Communicate(texto, VOZ)
    player = subprocess.Popen(
        ["ffplay", "-nodisp", "-autoexit", "-f", "mp3", "-"],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        async for chunk in communicate.stream():
            if _evento_interrupcion.is_set():
                player.kill()
                return
            if chunk["type"] == "audio":
                try:
                    player.stdin.write(chunk["data"])
                except (BrokenPipeError, OSError):
                    player.kill()
                    return
        player.stdin.close()
        # Polling — revisa interrupción cada 50ms mientras ffplay reproduce
        while player.poll() is None:
            if _evento_interrupcion.is_set():
                player.kill()
                return
            await asyncio.sleep(0.05)
    except Exception:
        player.kill()
        raise

def _monitor_keywords(evento_fin):
    """Escucha el micrófono buscando palabras de interrupción mientras Imai habla."""
    try:
        import modules.stt as stt_mod
    except ImportError:
        return

    modelo = stt_mod.model
    if modelo is None:
        return

    # doble del umbral calibrado para ignorar el bleedthrough del parlante
    umbral_monitor = max(stt_mod.umbral * 2, 350)
    sample_rate = 16000
    chunk_samples = int(1.5 * sample_rate)

    try:
        with sd.InputStream(samplerate=sample_rate, channels=1, dtype="int16") as stream:
            while not evento_fin.is_set() and not _evento_interrupcion.is_set():
                chunk, _ = stream.read(chunk_samples)
                rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))

                if rms < umbral_monitor:
                    continue

                # faster-whisper acepta numpy float32 directamente, sin archivo temporal
                audio_f32 = chunk.flatten().astype(np.float32) / 32768.0
                try:
                    segs, _ = modelo.transcribe(
                        audio_f32, language="es",
                        vad_filter=False,
                        beam_size=1,
                        condition_on_previous_text=False,
                    )
                    texto = _sin_acentos(" ".join(s.text for s in segs).lower().strip())
                    if any(k in texto for k in _KEYWORDS):
                        _log.info("Interrumpido")
                        _evento_interrupcion.set()
                except Exception:
                    pass
    except Exception:
        pass

def generar(texto):
    asyncio.run(_generar_async(texto))

def reproducir():
    _play(AUDIO_FILE)

async def _generar_async(texto):
    tts = edge_tts.Communicate(texto, VOZ)
    await tts.save(AUDIO_FILE)

def _play(archivo):
    if sys.platform == "win32":
        subprocess.run(["start", "/wait", archivo], shell=True)
    elif sys.platform == "darwin":
        subprocess.run(["afplay", archivo])
    else:
        subprocess.run(["mpg123", archivo])
