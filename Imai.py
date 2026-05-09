import re
import sys
import subprocess
import ollama
from stt import escuchar
from tts import hablar
from prompt import SYSTEM_PROMPT
from config import MODEL

MAX_TURNOS = 10

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

def main():
    limpiar()
    print("=" * 40)
    print("        IMAI  —  delta Crucis")
    print("=" * 40)
    print("  di 'salir' para terminar")
    print("=" * 40)
    print()
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
        print("Imai pensando...")

        try:
            response = ollama.chat(model=MODEL, messages=historial)
            respuesta = _limpiar_markdown(response["message"]["content"])
        except Exception as e:
            print(f"Error al consultar Ollama: {e}")
            hablar("Tuve un problema. Intenta de nuevo.")
            historial.pop()
            continue

        historial.append({"role": "assistant", "content": respuesta})
        print(f"Imai: {respuesta}")
        hablar(respuesta)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nSaliendo...")
