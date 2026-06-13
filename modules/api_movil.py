"""
Procesamiento de comandos de voz para el cliente móvil.
Recibe audio WebM del celular, transcribe, ejecuta, devuelve MP3.
"""
import asyncio
import os
import subprocess
import tempfile
import threading
import logging

from config import VOZ

_log = logging.getLogger(__name__)

_historial = []
_lock      = threading.Lock()

# ──────────────────────────────────────────────────────────────────────────────
# Audio
# ──────────────────────────────────────────────────────────────────────────────

def _ffmpeg_cmd():
    return "ffmpeg"

def _webm_a_wav(audio_bytes: bytes) -> str:
    """Convierte WebM/Opus → WAV 16kHz mono. Retorna ruta del WAV temporal."""
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
        f.write(audio_bytes)
        ruta_in = f.name
    ruta_out = ruta_in.replace(".webm", ".wav")
    subprocess.run(
        [_ffmpeg_cmd(), "-y", "-i", ruta_in, "-ar", "16000", "-ac", "1", ruta_out],
        capture_output=True,
    )
    os.unlink(ruta_in)
    return ruta_out

def _tts_bytes(texto: str) -> bytes:
    """Genera audio TTS y retorna bytes MP3 (no reproduce en el PC)."""
    import edge_tts

    async def _gen():
        chunks = []
        async for chunk in edge_tts.Communicate(texto, VOZ).stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])
        return b"".join(chunks)

    return asyncio.run(_gen())

# ──────────────────────────────────────────────────────────────────────────────
# Procesamiento principal
# ──────────────────────────────────────────────────────────────────────────────

def procesar(audio_bytes: bytes) -> tuple[str, bytes]:
    """
    Recibe bytes de audio WebM.
    Retorna (texto_transcrito, audio_mp3_respuesta).
    """
    # 1. Transcribir
    ruta_wav = _webm_a_wav(audio_bytes)
    try:
        from modules.stt import _transcribir
        texto, _ = _transcribir(ruta_wav)
    finally:
        try:
            os.unlink(ruta_wav)
        except Exception:
            pass

    if not texto or not texto.strip():
        return "", _tts_bytes("No entendí lo que dijiste.")

    # 2. Procesar con LLM (historial móvil propio, sin hablar por el PC)
    from modules.prompt import get_system_prompt
    from modules.claude_llm import consultar
    from modules.tools_def import ejecutar

    with _lock:
        if not _historial:
            _historial.append({"role": "system", "content": get_system_prompt()})

        _historial.append({"role": "user", "content": texto})

        # Mantener máximo 10 turnos
        sistema  = _historial[:1]
        mensajes = _historial[1:]
        if len(mensajes) > 20:
            mensajes = mensajes[-20:]
        historial_actual = sistema + mensajes

        respuesta = ""
        try:
            respuesta, tool_calls = consultar(historial_actual)  # sin hablar_cb

            if tool_calls:
                resultados = []
                for tc in tool_calls:
                    res = ejecutar(tc["function"]["name"], tc["function"]["arguments"])
                    if res:
                        resultados.append(res)
                respuesta = " ".join(resultados)

            _historial.append({"role": "assistant", "content": respuesta or "Listo."})

        except Exception as e:
            _log.error("api_movil error: %s", e)
            respuesta = "Tuve un problema procesando el comando."

    return texto, _tts_bytes(respuesta or "Listo.")
