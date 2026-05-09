import sounddevice as sd
import scipy.io.wavfile as wav
from faster_whisper import WhisperModel
SAMPLE_RATE = 16000
DURACION = 5
print("Cargando Whisper...")
model = WhisperModel("medium", device="cpu", compute_type="int8")
print("Whisper listo.")
def escuchar():
    print("Escuchando...")
    audio = sd.rec(
        int(DURACION * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16"
    )
    sd.wait()
    wav.write("temp.wav", SAMPLE_RATE, audio)
    segments, _ = model.transcribe("temp.wav", language="es")
    texto = " ".join([s.text for s in segments]).strip()
    return texto