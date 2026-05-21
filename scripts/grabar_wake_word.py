# -*- coding: utf-8 -*-
"""
Graba clips de "Imai" para entrenar el wake word.
Meta: 50 clips en condiciones variadas.
"""
import sys
import os
import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wav

# Forzar UTF-8 en la consola de Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

SAMPLE_RATE = 16000
DURACION    = 1.5
CARPETA     = "wake_word_data/imai"

os.makedirs(CARPETA, exist_ok=True)

ya_grabados = sorted(f for f in os.listdir(CARPETA) if f.endswith(".wav"))
i = len(ya_grabados)

GUIA = [
    (10, "VOZ NORMAL - di 'Imai' como lo dirias normalmente"),
    (10, "MAS CERCA  - acercate al microfono"),
    (10, "MAS LEJOS  - alejate un poco del microfono"),
    (10, "CON RUIDO  - pon musica baja o habla con ruido de fondo"),
    (10, "VARIACIONES - prueba: 'oye Imai', 'Imai!', 'eh Imai', distintos tonos"),
]

print("=" * 52)
print("   GRABADOR DE WAKE WORD - Imai")
print("=" * 52)
print(f"   Ya grabados: {i} clips")
print(f"   Carpeta: {CARPETA}")
print()
print("   Presiona Enter para grabar, Ctrl+C para salir.")
print("=" * 52)
print()

tramo_actual = 0

for total, descripcion in GUIA:
    if i >= sum(t for t, _ in GUIA):
        break

    tramo_actual += 1
    en_tramo      = 0

    print(f"\n-- Tanda {tramo_actual}/5: {descripcion} --")
    print(f"   Graba {total} clips en esta condicion.\n")

    while en_tramo < total:
        restantes = total - en_tramo
        try:
            input(f"  [{i+1:02d}/50] ({restantes} en tanda) -> Enter y di 'Imai'... ")
        except KeyboardInterrupt:
            print(f"\n\nGrabacion pausada. Total: {i} clips guardados.")
            raise SystemExit

        print("  [ REC ]", end="", flush=True)
        try:
            audio = sd.rec(
                int(DURACION * SAMPLE_RATE),
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="int16",
            )
            sd.wait()
        except Exception as e:
            print(f" Error: {e}")
            continue

        rms = np.sqrt(np.mean(audio.astype(np.float32) ** 2))
        if rms < 100:
            print(" (sin voz, intenta de nuevo)")
            continue

        ruta = os.path.join(CARPETA, f"imai_{i:03d}.wav")
        wav.write(ruta, SAMPLE_RATE, audio)
        print(f" OK - {ruta}  (RMS={rms:.0f})")
        i        += 1
        en_tramo += 1

print()
print("=" * 52)
print(f"   Listo. {i} clips guardados en '{CARPETA}'.")
print("   Siguiente paso: entrenar en Google Colab.")
print("=" * 52)
