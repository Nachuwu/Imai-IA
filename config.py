import os
from dotenv import load_dotenv

load_dotenv()

MODEL        = os.getenv("MODEL",        "mistral")
VOZ          = os.getenv("VOZ",          "es-CL-LorenzoNeural")

SAMPLE_RATE  = 16000
CHUNK        = 0.3
UMBRAL_RMS   = int(os.getenv("UMBRAL_RMS",   "300"))
SILENCIO_MAX = float(os.getenv("SILENCIO_MAX", "1.5"))
DURACION_MAX = int(os.getenv("DURACION_MAX",  "15"))

AUDIO_FILE   = "respuesta.mp3"
TEMP_WAV     = "temp.wav"
