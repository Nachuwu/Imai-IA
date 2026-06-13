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
    try:
        resultado = subprocess.run(
            [_ffmpeg_cmd(), "-y", "-i", ruta_in, "-ar", "16000", "-ac", "1", ruta_out],
            capture_output=True, timeout=30,
        )
    finally:
        os.unlink(ruta_in)

    if resultado.returncode != 0 or not os.path.exists(ruta_out):
        raise RuntimeError("ffmpeg no pudo convertir el audio recibido")
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

def procesar(audio_bytes: bytes) -> tuple[str, str, bytes]:
    """
    Recibe bytes de audio WebM.
    Retorna (texto_transcrito, texto_respuesta, audio_mp3_respuesta).
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
        msg = "No entendí lo que dijiste."
        return "", msg, _tts_bytes(msg)

    # 2. Procesar con LLM (historial móvil propio, sin hablar por el PC)
    from modules.prompt import get_system_prompt
    from modules.claude_llm import consultar
    from modules.tools_def import ejecutar

    with _lock:
        if not _historial:
            _historial.append({"role": "system", "content": get_system_prompt()})

        _historial.append({"role": "user", "content": texto})

        # Mantener máximo 10 turnos (1 system + 20 mensajes)
        historial_actual = _historial[:1] + _historial[-20:]

    # Fuera del lock: la llamada al LLM y la ejecución de tools pueden tardar
    # (red, o incluso esperar confirmación por voz en el PC) y no deben
    # bloquear otras requests del cliente móvil.
    try:
        respuesta, tool_calls = consultar(historial_actual)  # sin hablar_cb

        if tool_calls:
            resultados = []
            for tc in tool_calls:
                res = ejecutar(tc["function"]["name"], tc["function"]["arguments"])
                if res:
                    resultados.append(res)
            respuesta = " ".join(resultados)

    except Exception as e:
        _log.error("api_movil error: %s", e)
        respuesta = "Tuve un problema procesando el comando."

    respuesta = respuesta or "Listo."

    with _lock:
        _historial.append({"role": "assistant", "content": respuesta})
        if len(_historial) > 21:
            _historial[:] = _historial[:1] + _historial[-20:]

    return texto, respuesta, _tts_bytes(respuesta)
