import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wav
from faster_whisper import WhisperModel

SAMPLE_RATE = 16000
CHUNK        = 0.3    # segundos por bloque de análisis
SILENCIO_MAX = 1.5    # segundos de silencio para cortar
DURACION_MAX = 15     # tope de seguridad en segundos
UMBRAL_RMS   = 300    # energía mínima para considerar voz

print("Cargando Whisper...")
model = WhisperModel("medium", device="cpu", compute_type="int8")
print("Whisper listo.")

def _rms(chunk):
    return np.sqrt(np.mean(chunk.astype(np.float32) ** 2))

def escuchar():
    print("Escuchando... (habla cuando quieras)")
    chunk_samples   = int(CHUNK * SAMPLE_RATE)
    chunks_silencio_max = int(SILENCIO_MAX / CHUNK)
    chunks_max      = int(DURACION_MAX / CHUNK)

    grabando        = False
    chunks_silencio = 0
    frames          = []

    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16") as stream:
            for _ in range(chunks_max):
                chunk, _ = stream.read(chunk_samples)
                energia = _rms(chunk)

                if not grabando:
                    if energia > UMBRAL_RMS:
                        grabando = True
                        print("Voz detectada...")
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
        print(f"Error de micrófono: {e}")
        return ""

    if not frames:
        print("No se detectó voz.")
        return ""

    audio = np.concatenate(frames, axis=0)
    try:
        wav.write("temp.wav", SAMPLE_RATE, audio)
        segments, _ = model.transcribe("temp.wav", language="es")
        return " ".join([s.text for s in segments]).strip()
    except Exception as e:
        print(f"Error al transcribir: {e}")
        return ""
