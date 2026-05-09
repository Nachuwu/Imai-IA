import re
import sys
import queue
import subprocess
import threading
import ollama
from modules.stt import escuchar, inicializar as inicializar_stt
from modules.tts import hablar
from modules.prompt import SYSTEM_PROMPT
from config import MODEL

MAX_TURNOS  = 10
_RE_ORACION = re.compile(r'(?<=[.!?])\s+')

def limpiar():
    if sys.platform == "win32":
        subprocess.run("cls", shell=True)
    else:
        subprocess.run(["clear"])

def _truncar_historial(historial):
    sistema  = historial[:1]
    mensajes = historial[1:]
    if len(mensajes) > MAX_TURNOS * 2:
        mensajes = mensajes[-(MAX_TURNOS * 2):]
    return sistema + mensajes

def _limpiar_markdown(texto):
    texto = re.sub(r'\*\*(.+?)\*\*', r'\1', texto)
    texto = re.sub(r'\*(.+?)\*',     r'\1', texto)
    texto = re.sub(r'`(.+?)`',       r'\1', texto)
    texto = re.sub(r'^#{1,6}\s+',    '',    texto, flags=re.MULTILINE)
    texto = re.sub(r'^\s*[-*+]\s+',  '',    texto, flags=re.MULTILINE)
    texto = re.sub(r'^\s*\d+\.\s+',  '',    texto, flags=re.MULTILINE)
    return texto.strip()

def _consultar_ollama(historial):
    """
    Streaming con pipeline de oraciones:
    - Hilo principal: recibe chunks de Ollama y los muestra en pantalla.
    - Hilo reproductor: toma oraciones completas de la cola y las habla.
    Ambos corren en paralelo — el audio empieza en cuanto termina la primera oración.
    """
    cola = queue.Queue()

    def _reproductor():
        while True:
            oracion = cola.get()
            if oracion is None:
                break
            hablar(oracion)

    hilo = threading.Thread(target=_reproductor, daemon=True)
    hilo.start()

    buffer         = ""
    texto_completo = ""
    print("Imai: ", end="", flush=True)

    try:
        for chunk in ollama.chat(model=MODEL, messages=historial, stream=True,
                                  options={"num_ctx": 1024, "num_predict": 200}):
            parte = chunk["message"]["content"]
            buffer         += parte
            texto_completo += parte
            print(parte, end="", flush=True)

            # Extraer oraciones completas y enviarlas a la cola TTS
            while True:
                m = _RE_ORACION.search(buffer)
                if not m:
                    break
                oracion = _limpiar_markdown(buffer[:m.start() + 1])
                buffer  = buffer[m.end():]
                if oracion:
                    cola.put(oracion)

    except Exception as e:
        cola.put(None)
        hilo.join()
        raise e

    print()

    # Hablar el texto restante (última oración sin punto final, etc.)
    if buffer.strip():
        cola.put(_limpiar_markdown(buffer.strip()))

    cola.put(None)  # señal de fin al hilo reproductor
    hilo.join()

    return _limpiar_markdown(texto_completo)

def main():
    limpiar()
    print("=" * 40)
    print("        IMAI  —  delta Crucis")
    print("=" * 40)
    print("  di 'salir' para terminar")
    print("=" * 40)
    print()

    inicializar_stt()

    historial = [{"role": "system", "content": SYSTEM_PROMPT}]
    hablar("Hola, soy Imai. Listo para ayudarte.")

    while True:
        try:
            texto = escuchar()
        except KeyboardInterrupt:
            hablar("Hasta luego.")
            break

        if not texto:
            continue

        print(f"Tu: {texto}")
        if "salir" in texto.lower():
            hablar("Hasta luego.")
            break

        historial = _truncar_historial(historial)
        historial.append({"role": "user", "content": texto})

        try:
            respuesta = _consultar_ollama(historial)
        except Exception as e:
            print(f"\n[ Error al consultar Ollama: {e} ]")
            hablar("Tuve un problema. Intenta de nuevo.")
            historial.pop()
            continue

        historial.append({"role": "assistant", "content": respuesta})

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nSaliendo...")
