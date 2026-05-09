import asyncio
import os
import sounddevice as sd
import scipy.io.wavfile as wav
import edge_tts
from faster_whisper import WhisperModel

SAMPLE_RATE = 16000
DURACION = 5
VOZ = "es-CL-LorenzoNeural"

print("Cargando Whisper...")
model = WhisperModel("medium", device="cpu", compute_type="int8")
print("Modelo listo.")
print()

async def hablar(texto):
    tts = edge_tts.Communicate(texto, VOZ)
    await tts.save("eco.mp3")
    os.system("start eco.mp3")

print(f"Habla algo ({DURACION} segundos)...")
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
print(f"Escuche: {texto}")

asyncio.run(hablar(f"Escuché: {texto}"))