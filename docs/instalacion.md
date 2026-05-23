# Instalación de Imai desde cero

Guía paso a paso para Windows 10/11.

---

## 1. Requisitos previos

### Python 3.10+
Descarga desde [python.org](https://www.python.org/downloads/).  
Durante la instalación activa **"Add Python to PATH"**.

Verifica:
```
python --version
```

### ffmpeg
Necesario para reproducir audio (Edge TTS).

1. Descarga la build desde [gyan.dev/ffmpeg/builds](https://www.gyan.dev/ffmpeg/builds/) → `ffmpeg-release-essentials.zip`
2. Extrae y copia la carpeta a `C:\ffmpeg`
3. Agrega `C:\ffmpeg\bin` al PATH del sistema:
   - Inicio → "Variables de entorno" → `Path` → Nuevo → `C:\ffmpeg\bin`
4. Verifica: `ffmpeg -version`

Si prefieres no tocar el PATH, configura `FFMPEG_BIN` en el `.env` más adelante.

---

## 2. Clonar el repositorio

```bash
git clone https://github.com/Nachuwu/Imai-IA.git
cd Imai-IA
```

---

## 3. Crear entorno virtual e instalar dependencias

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

La instalación descarga ~1 GB la primera vez (modelos ML incluidos).

---

## 4. Configurar el entorno (.env)

Copia el archivo de ejemplo:
```bash
copy .env.example .env
```

Edita `.env` con tus claves:

### API keys mínimas

**Claude (obligatorio)** — la inteligencia de Imai:
1. Ve a [console.anthropic.com](https://console.anthropic.com) → API Keys → Create Key
2. Copia la key en `.env`:
   ```
   ANTHROPIC_API_KEY=sk-ant-api03-...
   ```

**Groq (recomendado)** — STT rápido en la nube:
1. Ve a [console.groq.com](https://console.groq.com) → API Keys
2. Copia la key en `.env`:
   ```
   GROQ_API_KEY=gsk_...
   ```
   Si lo dejas vacío, Imai usa Whisper local (más lento pero funciona).

### Ajustes opcionales

```env
CIUDAD=Santiago          # Ciudad para el clima
VOZ=es-CL-LorenzoNeural  # Voz de Edge TTS
WAKE_WORD=1              # 1=espera "escúchame", 0=siempre escucha
UMBRAL_RMS=150           # Sensibilidad del micrófono (baja si no detecta)
```

---

## 5. Modelo de voz Piper (TTS local, opcional)

Sin Piper, Imai usa Edge TTS que requiere internet. Con Piper la voz es local y más rápida.

1. Descarga los dos archivos:
   - [es_ES-davefx-medium.onnx](https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/davefx/medium/es_ES-davefx-medium.onnx)
   - [es_ES-davefx-medium.onnx.json](https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/davefx/medium/es_ES-davefx-medium.onnx.json)

2. Colócalos en la carpeta `models/`

3. Activa en `.env`:
   ```
   PIPER_MODEL=models/es_ES-davefx-medium.onnx
   ```

---

## 6. Google Calendar y Gmail (opcional)

Ambos usan el mismo archivo de credenciales OAuth.

### Crear credenciales en Google Cloud

1. Ve a [console.cloud.google.com](https://console.cloud.google.com)
2. Crea un proyecto nuevo (ej. "Imai")
3. En "APIs y servicios" → "Biblioteca":
   - Habilita **Google Calendar API**
   - Habilita **Gmail API**
4. Ve a "Credenciales" → "Crear credenciales" → **ID de cliente OAuth 2.0**
   - Tipo: **Aplicación de escritorio**
   - Nombre: cualquiera
5. Descarga el JSON generado y guárdalo como `data/calendar_credentials.json`

### Agregar tu cuenta como usuario de prueba

En "Pantalla de consentimiento de OAuth" → "Usuarios de prueba" → agrega tu email de Google.  
Esto es necesario mientras la app esté en modo de prueba.

### Activar en .env

```env
GOOGLE_CALENDAR_ENABLED=1
GMAIL_ENABLED=1
```

### Autorizar por primera vez

La primera vez que uses un comando de Calendar o Gmail, Imai abre el navegador para pedir permiso. Acepta y los tokens se guardan automáticamente en `data/`.

---

## 7. Primer arranque

```bash
venv\Scripts\activate
python Imai.py
```

Imai calibra el micrófono durante ~2 segundos al arrancar.

- **Con wake word activado** (`WAKE_WORD=1`): di "escúchame" para activarlo
- **Sin wake word** (`WAKE_WORD=0`): habla directamente
- El dashboard web está en **http://localhost:5000**
- Para salir: di "salir" o presiona `Ctrl+C`

### Si el micrófono no detecta nada

Baja el umbral en `.env`:
```env
UMBRAL_RMS=80
```

### Si el audio no suena

ffmpeg no está en el PATH. Configura:
```env
FFMPEG_BIN=C:\ffmpeg\bin
```

### Modo directo (sin wake word, para desarrollo)

```env
WAKE_WORD=0
```

---

## Dependencias principales

| Paquete | Uso |
|---------|-----|
| `anthropic` | Claude API — LLM y visión |
| `groq` | Whisper en la nube (STT) |
| `faster-whisper` | Whisper local (fallback STT) |
| `edge-tts` | Text-to-speech en la nube |
| `pyaudio` | Grabación de micrófono |
| `pyautogui` | Control de mouse y teclado |
| `pygetwindow` | Control de ventanas |
| `flask` | Dashboard web |
| `chromadb` | Base vectorial para memoria/RAG |
| `sentence-transformers` | Embeddings para búsqueda semántica |
| `apscheduler` | Recordatorios y alarmas |
| `google-api-python-client` | Calendar y Gmail API |
| `beautifulsoup4` | Extracción de texto web |
| `opencv-python` | Captura de webcam |
| `piper-tts` | TTS local (opcional) |
