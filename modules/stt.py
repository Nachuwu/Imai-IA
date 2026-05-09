import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wav
from faster_whisper import WhisperModel
from config import SAMPLE_RATE, CHUNK, SILENCIO_MAX, DURACION_MAX, UMBRAL_RMS, TEMP_WAV

model = None

def inicializar():
    global model
    print("Cargando Whisper...")
    model = WhisperModel("small", device="cpu", compute_type="int8")
    print("Whisper listo.\n")

def _rms(chunk):
    return np.sqrt(np.mean(chunk.astype(np.float32) ** 2))

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
                    if energia > UMBRAL_RMS:
                        grabando = True
                        print("\a[ ● Grabando ]", flush=True)
                        frames.append(chunk)
                else:
                    frames.append(chunk)
                    if energia < UMBRAL_RMS:
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
        segments, _ = model.transcribe(TEMP_WAV, language="es")
        return " ".join([s.text for s in segments]).strip()
    except Exception as e:
        print(f"[ Error al transcribir: {e} ]")
        return ""
