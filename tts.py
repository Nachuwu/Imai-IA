import asyncio
import sys
import subprocess
import edge_tts
from config import VOZ, AUDIO_FILE

async def _hablar(texto):
    tts = edge_tts.Communicate(texto, VOZ)
    await tts.save(AUDIO_FILE)
    _reproducir(AUDIO_FILE)

def _reproducir(archivo):
    if sys.platform == "win32":
        subprocess.run(["start", "/wait", archivo], shell=True)
    elif sys.platform == "darwin":
        subprocess.run(["afplay", archivo])
    else:
        subprocess.run(["mpg123", archivo])

def hablar(texto):
    try:
        asyncio.run(_hablar(texto))
    except Exception as e:
        print(f"Error en TTS: {e}")
        print(f"[Imai]: {texto}")
