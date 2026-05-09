import ollama
import os
from stt import escuchar
from tts import hablar
from prompt import SYSTEM_PROMPT

MAX_TURNOS = 10  # pares usuario+asistente que se conservan en el historial

def limpiar():
    os.system("cls")

def _truncar_historial(historial):
    sistema   = historial[:1]
    mensajes  = historial[1:]
    if len(mensajes) > MAX_TURNOS * 2:
        mensajes = mensajes[-(MAX_TURNOS * 2):]
    return sistema + mensajes

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
            response = ollama.chat(model="mistral", messages=historial)
            respuesta = response["message"]["content"]
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
