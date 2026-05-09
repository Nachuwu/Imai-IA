import asyncio
import edge_tts
import os

VOZ = "es-CL-LorenzoNeural"

async def _hablar(texto):
    tts = edge_tts.Communicate(texto, VOZ)
    await tts.save("respuesta.mp3")
    os.system("start /wait respuesta.mp3")

def hablar(texto):
    try:
        asyncio.run(_hablar(texto))
    except Exception as e:
        print(f"Error en TTS: {e}")
        print(f"[Imai]: {texto}")
