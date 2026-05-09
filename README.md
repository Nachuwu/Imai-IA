# Imai — Asistente de voz local

Imai es un asistente personal de voz que corre completamente en tu máquina. Escucha tu micrófono, transcribe lo que dices, consulta un modelo de lenguaje local y te responde en voz alta.

Su nombre viene de **Imai**, la estrella delta de la Cruz del Sur, visible desde Chile.

---

## Requisitos previos

- Python 3.10 o superior
- [Ollama](https://ollama.com) instalado y corriendo
- [ffmpeg](https://www.gyan.dev/ffmpeg/builds/) instalado (para reproducción de audio en streaming)

---

## Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/Imai-IA.git
cd Imai-IA
```

### 2. Crear entorno virtual e instalar dependencias

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / Mac
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Instalar ffmpeg

ffmpeg es necesario para reproducir el audio en streaming (menor latencia).

**Windows:**
1. Descarga `ffmpeg-release-essentials.zip` desde [gyan.dev/ffmpeg/builds](https://www.gyan.dev/ffmpeg/builds/)
2. Extrae el contenido, por ejemplo en `C:\ffmpeg\`
3. Agrega la ruta de la carpeta `bin\` al PATH del sistema, o configúrala en el `.env` (ver sección de configuración)

**Mac:**
```bash
brew install ffmpeg
```

**Linux:**
```bash
sudo apt install ffmpeg        # Debian/Ubuntu
sudo pacman -S ffmpeg          # Arch
```

### 4. Instalar el modelo de lenguaje en Ollama

```bash
ollama pull llama3.2:1b
```

> Puedes usar cualquier modelo disponible en [ollama.com/library](https://ollama.com/library). El modelo se configura en `.env`.

### 5. Configurar el entorno

Copia o edita el archivo `.env` en la raíz del proyecto:

```env
# Modelo de lenguaje (debe estar descargado en Ollama)
MODEL=llama3.2:1b

# Voz de Edge TTS
VOZ=es-CL-LorenzoNeural

# Ruta a ffmpeg/bin — solo si no está en el PATH del sistema
FFMPEG_BIN=C:\ruta\a\ffmpeg\bin

# Sensibilidad del micrófono (bajar si no detecta voz, subir si hay falsos positivos)
UMBRAL_RMS=150

# Segundos de silencio para cortar la grabación
SILENCIO_MAX=1.5

# Duración máxima de grabación en segundos
DURACION_MAX=15
```

---

## Uso

Asegúrate de que Ollama esté corriendo, luego:

```bash
python Imai.py
```

- **Habla** cuando aparezca `[ Escuchando... ]`
- Imai responde en voz cuando terminas de hablar
- Di **"salir"** o presiona `Ctrl+C` para cerrar

---

## Voces disponibles (Edge TTS)

| Código | Descripción |
|--------|-------------|
| `es-CL-LorenzoNeural` | Chile, masculino |
| `es-CL-CatalinaNeural` | Chile, femenino |
| `es-ES-AlvaroNeural` | España, masculino |
| `es-ES-ElviraNeural` | España, femenino |
| `es-MX-JorgeNeural` | México, masculino |
| `es-MX-DaliaNeural` | México, femenino |

Cambia la voz editando `VOZ=` en el `.env`.

---

## Estructura del proyecto

```
Imai-IA/
├── Imai.py              # Punto de entrada, loop principal
├── config.py            # Carga variables de entorno y constantes
├── .env                 # Configuración editable por el usuario
├── requirements.txt     # Dependencias Python
├── modules/
│   ├── stt.py           # Grabación y transcripción de voz (Whisper)
│   ├── tts.py           # Síntesis y reproducción de voz (Edge TTS)
│   └── prompt.py        # Personalidad y reglas de Imai
└── audio/               # Archivos de audio temporales (generados en runtime)
```

---

## Solución de problemas

**`[ Sin voz detectada ]` constantemente**
Baja el valor de `UMBRAL_RMS` en `.env` (ej. `100`).

**El audio no suena / error con `respuesta.mp3`**
ffmpeg no está siendo encontrado. Agrega la ruta de la carpeta `bin\` de ffmpeg en `FFMPEG_BIN` dentro del `.env`.

**Error de micrófono al iniciar**
Verifica que el micrófono esté conectado y que Python tenga permisos para acceder a él.

**Ollama no responde**
Asegúrate de que el servicio de Ollama esté corriendo (`ollama serve`) y de que el modelo configurado en `MODEL` esté descargado (`ollama list`).

**Warning de Hugging Face al cargar Whisper**
Es normal la primera vez que se descarga un modelo. Una vez cacheado no vuelve a aparecer. El `.env` ya incluye `HF_HUB_OFFLINE=1` para evitar conexiones innecesarias.
