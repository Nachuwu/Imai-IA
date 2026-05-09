import ollama
import os

SYSTEM_PROMPT = """
Eres Imai, un asistente personal inteligente.
Tu nombre viene de la estrella delta de la Cruz del Sur.
Respondes siempre en español, de forma directa y concisa.
"""

def limpiar_pantalla():
    os.system("cls" if os.name == "nt" else "clear")

def main():
    limpiar_pantalla()
    print("=" * 40)
    print("        IMAI  —  δ Crucis")
    print("=" * 40)
    print("  escribe 'salir' para terminar")
    print("  escribe 'limpiar' para resetear")
    print("=" * 40)
    print()

    historial = [{"role": "system", "content": SYSTEM_PROMPT}]

    while True:
        user_input = input("Tú: ").strip()

        if not user_input:
            continue
        if user_input.lower() == "salir":
            print("\nImai: Hasta luego.\n")
            break
        if user_input.lower() == "limpiar":
            historial = [{"role": "system", "content": SYSTEM_PROMPT}]
            limpiar_pantalla()
            print("Conversación reiniciada.\n")
            continue

        historial.append({"role": "user", "content": user_input})

        print("Imai: ", end="", flush=True)
        respuesta_completa = ""

        stream = ollama.chat(
            model="mistral",
            messages=historial,
            stream=True
        )

        for chunk in stream:
            texto = chunk["message"]["content"]
            print(texto, end="", flush=True)
            respuesta_completa += texto

        print("\n")
        historial.append({"role": "assistant", "content": respuesta_completa})

if __name__ == "__main__":
    main()