import sounddevice as sd
import scipy.io.wavfile as wav
from faster_whisper import WhisperModel

DURACION = 5
SAMPLE_RATE = 16000

print("Cargando Whisper...")
model = WhisperModel("medium", device="cpu", compute_type="int8")
print("Modelo listo.")
print()
print(f"Grabando {DURACION} segundos... habla ahora")

audio = sd.rec(
    int(DURACION * SAMPLE_RATE),
    samplerate=SAMPLE_RATE,
    channels=1,
    dtype="int16"
)
sd.wait()
print("Grabacion terminada.")

wav.write("temp.wav", SAMPLE_RATE, audio)

segments, _ = model.transcribe("temp.wav", language="es")
texto = " ".join([s.text for s in segments])

print()
print(f"Transcripcion: {texto}")