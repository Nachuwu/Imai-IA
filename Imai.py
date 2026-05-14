import re
import sys
import time
import queue
import subprocess
import threading
import ollama
from modules.stt import escuchar, inicializar as inicializar_stt, esta_pausado, pausar as pausar_micro
from modules.tts import hablar, fue_interrumpido
from modules.prompt import SYSTEM_PROMPT
from modules.intent import detectar
import modules.apps as apps
import modules.tools as tools
import modules.urls as urls
import modules.historial as log
from config import MODEL, CIUDAD

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

def manejar_herramienta(texto):
    """
    Evalúa si el texto es un comando de herramienta.
    Retorna True si lo manejó, False si debe ir al LLM.
    """
    intent, objeto = detectar(texto)

    if intent == "abrir":
        key = apps.abrir(objeto or "")
        hablar(f"Abriendo {key}." if key else f"No encontré {objeto}.")
        return True

    if intent == "cerrar":
        key = apps.cerrar(objeto or "")
        hablar(f"Cerrando {key}." if key else f"No encontré {objeto} ejecutándose.")
        return True

    if intent == "volumen":
        if isinstance(objeto, int):
            hablar(tools.set_volumen(objeto))
        elif objeto == "subir":
            hablar(tools.subir_volumen())
        elif objeto == "bajar":
            hablar(tools.bajar_volumen())
        elif objeto == "silenciar":
            hablar(tools.silenciar())
        elif objeto == "activar":
            hablar(tools.activar_sonido())
        else:
            hablar(tools.get_volumen())
        return True

    if intent == "timer":
        if objeto:
            def _cb_timer(msg):
                tools.notificar("Imai — Timer", msg)
                hablar(msg)
            hablar(tools.crear_timer(objeto, _cb_timer))
        else:
            hablar("¿De cuántos segundos o minutos el timer?")
        return True

    if intent == "buscar":
        hablar(f"Buscando {objeto}.")
        tools.buscar_archivos(objeto or "", callback=hablar)
        return True

    if intent == "hora":
        hablar(tools.get_hora())
        return True

    if intent == "fecha":
        hablar(tools.get_fecha())
        return True

    if intent == "clima":
        ciudad = objeto or CIUDAD
        hablar(tools.get_clima(ciudad))
        return True

    if intent == "calcular":
        if objeto:
            resultado = tools.calcular(objeto)
            hablar(f"{resultado}." if resultado else "No pude calcular eso.")
        else:
            hablar("¿Qué quieres calcular?")
        return True

    if intent == "portapapeles":
        hablar(tools.get_portapapeles())
        return True

    if intent == "captura":
        hablar(tools.captura_pantalla())
        return True

    if intent == "spotify":
        if objeto == "siguiente":    respuesta = tools.spotify_siguiente()
        elif objeto == "anterior":   respuesta = tools.spotify_anterior()
        elif objeto == "pausa":      respuesta = tools.spotify_play_pause()
        elif objeto == "parar":      respuesta = tools.spotify_parar()
        elif objeto == "que_suena":  respuesta = tools.get_cancion_spotify()
        else:                        respuesta = tools.spotify_play_pause()
        hablar(respuesta)
        return True

    if intent == "brillo":
        if isinstance(objeto, int):   hablar(tools.set_brillo(objeto))
        elif objeto == "subir":       hablar(tools.subir_brillo())
        elif objeto == "bajar":       hablar(tools.bajar_brillo())
        else:                         hablar(tools.get_brillo())
        return True

    if intent == "url":
        hablar(urls.manejar(objeto or texto))
        return True

    if intent == "no_molestar":
        if objeto:
            pausar_micro(objeto)
            def _reanudar(msg):
                hablar("Ya puedes hablarme.")
            tools.crear_timer(objeto, _reanudar)
            hablar(f"De acuerdo, silencio por {tools._fmt_tiempo(objeto)}.")
        else:
            hablar("¿Por cuánto tiempo?")
        return True

    return False

def _consultar_ollama(historial):
    cola         = queue.Queue()
    interrumpido = threading.Event()

    def _reproductor():
        while True:
            oracion = cola.get()
            if oracion is None:
                break
            hablar(oracion)
            if fue_interrumpido():
                interrumpido.set()
                while True:
                    try:
                        cola.get_nowait()
                    except queue.Empty:
                        break
                break

    hilo = threading.Thread(target=_reproductor, daemon=True)
    hilo.start()

    buffer         = ""
    texto_completo = ""
    print("Imai: ", end="", flush=True)

    try:
        for chunk in ollama.chat(model=MODEL, messages=historial, stream=True,
                                  options={"num_ctx": 1024, "num_predict": 200}):
            if interrumpido.is_set():
                break

            parte = chunk["message"]["content"]
            buffer         += parte
            texto_completo += parte
            print(parte, end="", flush=True)

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

    if buffer.strip() and not interrumpido.is_set():
        cola.put(_limpiar_markdown(buffer.strip()))

    cola.put(None)
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
    apps.escanear_en_segundo_plano()

    historial = [{"role": "system", "content": SYSTEM_PROMPT}]
    hablar("Hola, soy Imai. Listo para ayudarte.")

    while True:
        try:
            if esta_pausado():
                time.sleep(0.5)
                continue
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

        # Herramientas primero — si matchea no va al LLM
        intent, _ = detectar(texto)
        if manejar_herramienta(texto):
            log.registrar(texto, intent, "")
            continue

        historial = _truncar_historial(historial)
        historial.append({"role": "user", "content": texto})

        try:
            respuesta = _consultar_ollama(historial)
        except Exception as e:
            print(f"\n[ Error al consultar Ollama: {e} ]")
            hablar("Tuve un problema. Intenta de nuevo.")
            historial.pop()
            continue

        if fue_interrumpido():
            historial.pop()
            hablar("Okay.")
            continue

        historial.append({"role": "assistant", "content": respuesta})
        log.registrar(texto, "llm", respuesta)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nSaliendo...")
