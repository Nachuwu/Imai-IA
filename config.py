import os
from dotenv import load_dotenv

load_dotenv()

# Si se define FFMPEG_BIN en .env, lo agrega al PATH del proceso actual
_ffmpeg_bin = os.getenv("FFMPEG_BIN", "")
if _ffmpeg_bin and _ffmpeg_bin not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _ffmpeg_bin + os.pathsep + os.environ.get("PATH", "")

MODEL         = os.getenv("MODEL",         "mistral")
GROQ_API_KEY  = os.getenv("GROQ_API_KEY",  "")
CIUDAD        = os.getenv("CIUDAD",        "Santiago")
VOZ           = os.getenv("VOZ",           "es-CL-LorenzoNeural")
PIPER_MODEL   = os.getenv("PIPER_MODEL",   "")   # ruta al .onnx de Piper
WAKE_WORD     = os.getenv("WAKE_WORD",     "1")   # "0" para desactivar

SAMPLE_RATE  = 16000
CHUNK        = 0.3
UMBRAL_RMS   = int(os.getenv("UMBRAL_RMS",   "300"))
SILENCIO_MAX = float(os.getenv("SILENCIO_MAX", "1.5"))
DURACION_MAX = int(os.getenv("DURACION_MAX",  "15"))

AUDIO_FILE   = "audio/respuesta.mp3"
TEMP_WAV     = "audio/temp.wav"
