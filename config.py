import os
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

load_dotenv()

# Rutas base del proyecto
_ROOT    = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(_ROOT, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Logging — archivo rotativo (sobrevive aunque corra sin consola, vía pythonw.exe)
LOG_FILE = os.path.join(DATA_DIR, "imai.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        RotatingFileHandler(LOG_FILE, maxBytes=2_000_000, backupCount=3, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

# Si se define FFMPEG_BIN en .env, lo agrega al PATH del proceso actual
_ffmpeg_bin = os.getenv("FFMPEG_BIN", "")
if _ffmpeg_bin and _ffmpeg_bin not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _ffmpeg_bin + os.pathsep + os.environ.get("PATH", "")

GROQ_API_KEY       = os.getenv("GROQ_API_KEY",       "")
ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY",  "")
CLAUDE_MODEL       = os.getenv("CLAUDE_MODEL",        "claude-haiku-4-5-20251001")
CIUDAD             = os.getenv("CIUDAD",              "Santiago")
VOZ                = os.getenv("VOZ",                 "es-CL-LorenzoNeural")
PIPER_MODEL        = os.getenv("PIPER_MODEL",         "")
WAKE_WORD          = os.getenv("WAKE_WORD",           "1")
WAKE_WORD_TARGET   = os.getenv("WAKE_WORD_TARGET",    "imai").lower().strip()
_ww_model_rel      = os.getenv("WAKE_WORD_MODEL", "models/imai.onnx")
WAKE_WORD_MODEL    = os.path.join(_ROOT, _ww_model_rel) if _ww_model_rel else ""

GOOGLE_CALENDAR_ENABLED = os.getenv("GOOGLE_CALENDAR_ENABLED", "0") == "1"
GMAIL_ENABLED           = os.getenv("GMAIL_ENABLED",           "0") == "1"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID",   "")

SAMPLE_RATE  = 16000
CHUNK        = 0.3
UMBRAL_RMS   = int(os.getenv("UMBRAL_RMS",   "300"))
SILENCIO_MAX = float(os.getenv("SILENCIO_MAX", "1.5"))
DURACION_MAX = int(os.getenv("DURACION_MAX",  "15"))

AUDIO_FILE   = "audio/respuesta.mp3"
TEMP_WAV     = "audio/temp.wav"
