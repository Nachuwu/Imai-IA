import asyncio
import sys
import subprocess
import shutil
import edge_tts
from config import VOZ, AUDIO_FILE

def hablar(texto):
    if shutil.which("ffplay"):
        try:
            asyncio.run(_streaming(texto))
            return
        except Exception as e:
            print(f"[ TTS streaming falló, usando fallback: {e} ]")
    try:
        generar(texto)
        reproducir()
    except Exception as e:
        print(f"[ Error en TTS: {e} ]")
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
            if chunk["type"] == "audio":
                player.stdin.write(chunk["data"])
        player.stdin.close()
        player.wait()
    except Exception:
        player.kill()
        raise

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
