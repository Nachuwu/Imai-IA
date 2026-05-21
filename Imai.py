import re
import sys
import time
import subprocess
from modules.stt import escuchar, inicializar as inicializar_stt, esta_pausado, esperar_wake_word
from modules.tts import hablar, fue_interrumpido
from modules.prompt import get_system_prompt
from modules.intent import detectar
import modules.apps as apps
import modules.tools as tools
import modules.urls as urls
import modules.historial as log
import modules.memoria as memoria
from modules.tools_def import ejecutar as ejecutar_tool
from modules.claude_llm import consultar as claude_consultar
from modules.rag import indexar_historial, buscar as rag_buscar, es_consulta_historial
import modules.recordatorios as recordatorios
import modules.dashboard as dashboard
from config import CIUDAD, WAKE_WORD

MAX_TURNOS = 10
_ultima_respuesta = ""

_SEP_COMANDOS = re.compile(
    r'\s+(?:y|luego|despu[eé]s|tambi[eé]n|adem[aá]s)\s+',
    re.IGNORECASE,
)

def _split_comandos(texto):
    """Divide comandos encadenados por 'y', 'luego', 'después', etc."""
    partes = [p.strip() for p in _SEP_COMANDOS.split(texto) if p.strip()]
    return partes if len(partes) > 1 else [texto]

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

# ---------------------------------------------------------------------------
# Fast path — regex para comandos claros sin pasar por el LLM
# ---------------------------------------------------------------------------

def manejar_herramienta(texto):
    intent, objeto = detectar(texto)

    if intent == "abrir":
        key = apps.abrir(objeto or "")
        hablar(f"Abriendo {key}." if key else f"No encontré {objeto}.")
        return True, intent, objeto

    if intent == "cerrar":
        key = apps.cerrar(objeto or "")
        hablar(f"Cerrando {key}." if key else f"No encontré {objeto} ejecutándose.")
        return True, intent, objeto

    if intent == "volumen":
        if isinstance(objeto, int):   hablar(tools.set_volumen(objeto))
        elif objeto == "subir":       hablar(tools.subir_volumen())
        elif objeto == "bajar":       hablar(tools.bajar_volumen())
        elif objeto == "silenciar":   hablar(tools.silenciar())
        elif objeto == "activar":     hablar(tools.activar_sonido())
        else:                         hablar(tools.get_volumen())
        return True, intent, objeto

    if intent == "timer":
        if objeto:
            def _cb(msg):
                tools.notificar("Imai — Timer", msg)
                hablar(msg)
            hablar(tools.crear_timer(objeto, _cb))
        else:
            hablar("¿De cuántos segundos o minutos el timer?")
        return True, intent, objeto

    if intent == "buscar":
        hablar(f"Buscando {objeto}.")
        tools.buscar_archivos(objeto or "", callback=hablar)
        return True, intent, objeto

    if intent == "hora":
        hablar(tools.get_hora())
        return True, intent, objeto

    if intent == "fecha":
        hablar(tools.get_fecha())
        return True, intent, objeto

    if intent == "clima":
        hablar(tools.get_clima(objeto or CIUDAD))
        return True, intent, objeto

    if intent == "calcular":
        if objeto:
            r = tools.calcular(objeto)
            hablar(f"{r}." if r else "No pude calcular eso.")
        else:
            hablar("¿Qué quieres calcular?")
        return True, intent, objeto

    if intent == "portapapeles":
        hablar(tools.get_portapapeles())
        return True, intent, objeto

    if intent == "captura":
        hablar(tools.captura_pantalla())
        return True, intent, objeto

    if intent == "spotify":
        if objeto == "siguiente":   hablar(tools.spotify_siguiente())
        elif objeto == "anterior":  hablar(tools.spotify_anterior())
        elif objeto == "pausa":     hablar(tools.spotify_play_pause())
        elif objeto == "parar":     hablar(tools.spotify_parar())
        elif objeto == "que_suena": hablar(tools.get_cancion_spotify())
        else:                       hablar(tools.spotify_play_pause())
        return True, intent, objeto

    if intent == "brillo":
        if isinstance(objeto, int): hablar(tools.set_brillo(objeto))
        elif objeto == "subir":     hablar(tools.subir_brillo())
        elif objeto == "bajar":     hablar(tools.bajar_brillo())
        else:                       hablar(tools.get_brillo())
        return True, intent, objeto

    if intent == "url":
        hablar(urls.manejar(objeto or texto))
        return True, intent, objeto

    if intent == "no_molestar":
        if objeto:
            from modules.stt import pausar as _pausar
            _pausar(objeto)
            def _reanudar(msg): hablar("Ya puedes hablarme.")
            tools.crear_timer(objeto, _reanudar)
            hablar(f"De acuerdo, silencio por {tools._fmt_tiempo(objeto)}.")
        else:
            hablar("¿Por cuánto tiempo?")
        return True, intent, objeto

    if intent == "cancelar_timer":
        hablar(tools.cancelar_timer())
        return True, intent, objeto

    if intent == "repetir":
        if _ultima_respuesta:
            hablar(_ultima_respuesta)
        else:
            hablar("No tengo nada que repetir todavía.")
        return True, intent, objeto

    if intent == "memoria":
        hecho = memoria.extraer_hecho(texto)
        if hecho:
            memoria.agregar(hecho)
            hablar(f"Anotado: {hecho}.")
        else:
            hablar("¿Qué quieres que recuerde?")
        return True, intent, objeto

    return False, intent, objeto

# ---------------------------------------------------------------------------
# LLM con tool calling — para comandos ambiguos y conversación
# ---------------------------------------------------------------------------

def _hablar_y_recordar(texto):
    global _ultima_respuesta
    _ultima_respuesta = texto
    hablar(texto)

def _hablar_streaming(oracion):
    global _ultima_respuesta
    _ultima_respuesta = oracion
    if not fue_interrumpido():
        hablar(oracion)

def _resumen_matutino():
    import modules.calendario as calendario
    hora  = tools.get_hora()
    clima = tools.get_clima(CIUDAD)
    recs  = recordatorios.listar()
    partes = [hora, clima]
    if "No tienes" not in recs and "No hay" not in recs:
        partes.append(recs)
    try:
        eventos = calendario.ver_eventos_hoy()
        if "No tienes eventos" not in eventos and "no está configurado" not in eventos:
            partes.append(eventos)
    except Exception:
        pass
    hablar(" ".join(partes))


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
    indexar_historial()
    memoria.indexar_existentes()
    recordatorios.inicializar(hablar)
    dashboard.iniciar()

    system_prompt = get_system_prompt()
    historial = [{"role": "system", "content": system_prompt}]
    _resumen_matutino()

    import winsound
    _turnos_conv = 0

    while True:
        try:
            if esta_pausado():
                time.sleep(0.5)
                continue
            if WAKE_WORD == "1":
                if _turnos_conv > 0:
                    _turnos_conv -= 1
                    winsound.Beep(660, 80)   # beep suave = modo conversación activo
                else:
                    esperar_wake_word()
                    winsound.Beep(880, 120)  # beep alto = wake word detectado
            texto, idioma = escuchar()
        except KeyboardInterrupt:
            hablar("Hasta luego.")
            break

        if not texto:
            _turnos_conv = 0
            continue

        print(f"Tu: {texto}")
        if "salir" in texto.lower():
            hablar("Hasta luego.")
            break

        # Fast path — ejecuta los comandos que reconoce, acumula el resto para LLM
        textos    = _split_comandos(texto)
        llm_partes = []
        for t in textos:
            manejado, intent, objeto = manejar_herramienta(t)
            if manejado:
                log.guardar(
                    messages=[
                        {"role": "system",    "content": system_prompt},
                        {"role": "user",      "content": t},
                        {"role": "assistant", "content": ""},
                    ],
                    intent=intent, objeto=objeto, herramienta=True,
                )
            else:
                llm_partes.append(t)

        if not llm_partes:
            _turnos_conv = 2
            continue

        # Si solo algunos fueron al fast path, LLM procesa el resto
        if len(llm_partes) < len(textos):
            texto = " y ".join(llm_partes)

        # LLM path — conversación y comandos ambiguos
        historial = _truncar_historial(historial)

        contenido_usuario = texto
        if idioma and idioma != "es":
            contenido_usuario = f"[Responde en {idioma}]\n{texto}"
        if es_consulta_historial(texto):
            fragmentos = rag_buscar(texto, n=3)
            if fragmentos:
                contexto = "\n---\n".join(fragmentos)
                contenido_usuario = f"Contexto de conversaciones anteriores:\n{contexto}\n\nPregunta: {contenido_usuario}"

        historial.append({"role": "user", "content": contenido_usuario})

        try:
            respuesta, tool_calls = claude_consultar(historial, hablar_cb=_hablar_streaming)
        except Exception as e:
            print(f"\n[ Error al consultar Claude: {e} ]")
            winsound.Beep(300, 400)
            hablar("Tuve un problema. Intenta de nuevo.")
            historial.pop()
            continue

        if tool_calls:
            resultados = []
            for tc in tool_calls:
                nombre = tc["function"]["name"]
                args   = tc["function"]["arguments"]
                print(f"[ Tool: {nombre} ]")
                resultado = ejecutar_tool(nombre, args, hablar_cb=hablar)
                if resultado:
                    _hablar_y_recordar(resultado)
                resultados.append(resultado)
                if nombre in ("guardar_memoria", "guardar_perfil", "actualizar_memoria"):
                    system_prompt = get_system_prompt()
                    historial[0]  = {"role": "system", "content": system_prompt}
                log.guardar(
                    messages=[
                        {"role": "system",    "content": system_prompt},
                        {"role": "user",      "content": texto},
                        {"role": "assistant", "content": resultado},
                    ],
                    intent=nombre, objeto=str(args), herramienta=True,
                )
            historial.append({"role": "assistant", "content": " ".join(resultados)})
            if nombre not in ("actualizar_memoria", "guardar_memoria"):
                _turnos_conv = 2
            continue

        if fue_interrumpido():
            historial.pop()
            hablar("Okay.")
            continue

        historial.append({"role": "assistant", "content": respuesta})
        _turnos_conv = 2
        log.guardar(
            messages=historial[-(MAX_TURNOS * 2):],
            intent="ninguna",
            herramienta=False,
        )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nSaliendo...")
