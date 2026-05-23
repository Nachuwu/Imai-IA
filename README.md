# Imai — Asistente de voz personal

Imai es un asistente personal de voz en español que corre en tu máquina. Escucha tu micrófono, transcribe lo que dices con Whisper, ejecuta comandos directos o consulta Claude (Anthropic) como LLM, y te responde en voz alta.

Su nombre viene de **Imai**, la estrella delta de la Cruz del Sur, visible desde Chile.

---

## Qué puede hacer

### Control del sistema
| Comando | Ejemplo |
|---------|---------|
| Volumen | "sube el volumen", "pon el volumen al 40", "silencia" |
| Brillo | "sube el brillo", "pon el brillo al 60" |
| Aplicaciones | "abre chrome", "cierra spotify" |
| Ventanas | "minimiza la ventana", "maximiza chrome", "cambia de ventana" |
| Control del PC | "apaga el PC en 10 segundos", "bloquea la pantalla", "suspende" |
| Captura de pantalla | "toma una captura de pantalla" |
| Portapapeles | "¿qué tengo copiado?" |

### Mouse y teclado
| Comando | Ejemplo |
|---------|---------|
| Escribir texto | "escribe hola mundo" |
| Presionar teclas | "presiona enter", "presiona control c", "presiona alt f4" |
| Scroll | "haz scroll abajo", "sube tres páginas" |
| Clic por coordenadas | "haz clic en 500, 300" |
| Clic por texto | "haz clic en Aceptar" (Claude Vision localiza el botón) |
| **Modo dictar** | "empieza a dictar" → todo lo que digas se escribe en la app activa |

En modo dictar, puedes decir símbolos: **"punto"** → `.` · **"coma"** → `,` · **"nueva línea"** → Enter · **"dos puntos"** → `:` · **"abre paréntesis"** → `(` · Para salir: **"para de dictar"**

### Música y medios
| Comando | Ejemplo |
|---------|---------|
| Spotify | "siguiente canción", "pausa la música", "¿qué está sonando?" |
| Historial Spotify | "¿qué canciones estuve escuchando?" |
| YouTube | "pon una canción de Bad Bunny en YouTube" |
| Sitios web | "abre GitHub", "busca recetas en Google" |

### Información
| Comando | Ejemplo |
|---------|---------|
| Hora y fecha | "¿qué hora es?", "¿qué día es hoy?" |
| Clima | "¿cómo está el clima en Santiago?" |
| Calculadora | "¿cuánto es 20% de 350?" |
| Búsqueda web | "busca qué es la fusión nuclear" |
| Analizar pantalla | "¿qué hay en pantalla?", "describe lo que estoy viendo" |
| Leer página web | "léeme esto", "resume esta página", "¿qué dice aquí sobre X?" |

### Organización
| Comando | Ejemplo |
|---------|---------|
| Recordatorios puntuales | "recuérdame tomar agua mañana a las 8" |
| Alarmas recurrentes | "ponme una alarma todos los días a las 7", "alarma de lunes a viernes a las 8" |
| Listar / cancelar | "¿qué recordatorios tengo?", "cancela el último recordatorio" |
| Timers | "pon un timer de 2 minutos" |
| Buscar archivos | "busca el archivo presupuesto" |
| Modo no molestar | "silencio por 10 minutos" |

### Google Calendar
| Comando | Ejemplo |
|---------|---------|
| Ver eventos del día | "¿qué tengo hoy?", "¿tengo algo agendado?" |
| Crear evento | "agéndame dentista el viernes a las 10", "crea un evento reunión mañana a las 3" |

### Gmail
| Comando | Ejemplo |
|---------|---------|
| Leer correos | "léeme los últimos correos", "¿tengo correos nuevos?" |
| Enviar correo | "manda un correo a fulano@gmail.com asunto hola mensaje probando" |

### Memoria y contexto
| Función | Ejemplo |
|---------|---------|
| Guardar datos personales | "me llamo Ignacio", "tengo 25 años", "trabajo de desarrollador" |
| Guardar hechos | "recuerda que me gusta el café negro" |
| Búsqueda semántica | "¿qué recuerdas sobre mis reuniones?" |
| Historial con RAG | "¿recuerdas lo que hablamos ayer?" |

### Comandos encadenados
```
"sube el volumen y abre chrome"
"pausa la música y después pon un timer de 5 minutos"
"toma una captura y dime qué hay en pantalla"
```

---

## Arquitectura

```
Micrófono → Wake word → STT → Intención → Herramienta O Claude LLM → TTS → Parlante
```

| Componente | Tecnología |
|------------|------------|
| Wake word | Whisper sliding window + rapidfuzz fuzzy matching |
| STT | Groq `whisper-large-v3` (nube) + faster-whisper `small` (local fallback) |
| Idioma | Español forzado en STT — Imai siempre escucha y responde en español |
| Detección de intención | Regex rápido, Claude LLM para casos ambiguos |
| LLM | Claude API (Anthropic) — `claude-haiku-4-5-20251001` |
| TTS | Piper TTS (local) → Edge TTS (nube) → pyttsx3 (fallback) |
| Visión | Claude Vision con captura de pantalla vía Pillow |
| Búsqueda web | DuckDuckGo Instant Answer API (sin API key) |
| Control de ventanas | pygetwindow + rapidfuzz |
| Mouse / teclado | pyautogui + Claude Vision para clic por texto |
| Recordatorios | APScheduler con persistencia JSON (puntuales y recurrentes) |
| Google Calendar | Google Calendar API v3 con OAuth |
| Gmail | Gmail API v1 con OAuth |
| Memoria | JSON estructurado (perfil + hechos) + ChromaDB vectorial |
| Historial | JSONL por día en formato ChatML + últimas 3 turns persistidas entre sesiones |
| RAG | ChromaDB + sentence-transformers |
| Dashboard | Flask en `http://localhost:5000` |

---

## Requisitos previos

- Python 3.10 o superior
- [ffmpeg](https://www.gyan.dev/ffmpeg/builds/) instalado y en el PATH
- Cuenta en [Anthropic](https://console.anthropic.com) para la API key (Claude)
- Cuenta en [Groq](https://console.groq.com) para STT en la nube (opcional pero recomendado)

---

## Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/Nachuwu/Imai-IA.git
cd Imai-IA
```

### 2. Crear entorno virtual e instalar dependencias

```bash
python -m venv venv
venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

### 3. Configurar el entorno

Crea un archivo `.env` en la raíz del proyecto:

```env
# LLM — Claude API (Anthropic)
ANTHROPIC_API_KEY=sk-ant-api03-...

# STT — Groq API para Whisper en la nube (opcional pero recomendado)
GROQ_API_KEY=gsk_...

# Ciudad por defecto para el clima
CIUDAD=Santiago

# Voz de Edge TTS (si no usas Piper)
VOZ=es-CL-LorenzoNeural

# Ruta a ffmpeg/bin (solo si no está en el PATH del sistema)
FFMPEG_BIN=C:\ruta\a\ffmpeg\bin

# Piper TTS local (ver sección de TTS)
PIPER_MODEL=models/es_ES-davefx-medium.onnx

# Wake word: "1" espera que digas "escúchame", "0" escucha directo
WAKE_WORD=1
WAKE_WORD_MODEL=          # vacío = usar Whisper; o ruta a modelo .onnx
WAKE_WORD_TARGET=escuchame

# Google Calendar y Gmail (mismas credenciales OAuth)
GOOGLE_CALENDAR_ENABLED=1
GMAIL_ENABLED=1

# Sensibilidad del micrófono
UMBRAL_RMS=150
SILENCIO_MAX=1.5
DURACION_MAX=15
```

### 4. Modelo de voz Piper (TTS local)

Descarga `es_ES-davefx-medium.onnx` y `es_ES-davefx-medium.onnx.json` desde [rhasspy/piper/releases](https://github.com/rhasspy/piper/releases) y colócalos en `models/`.

### 5. Google Calendar y Gmail (opcional)

1. Ve a [console.cloud.google.com](https://console.cloud.google.com) → crea un proyecto
2. Habilita **Google Calendar API** y **Gmail API**
3. Crea credenciales **OAuth 2.0 → Aplicación de escritorio**
4. Descarga el JSON y guárdalo como `data/calendar_credentials.json`
5. En "Pantalla de consentimiento de OAuth" agrega tu email como usuario de prueba
6. La primera vez que uses Calendar o Gmail se abre el navegador para autorizar — los tokens se guardan automáticamente en `data/`

---

## Uso

```bash
python Imai.py
```

1. Imai calibra el micrófono al arrancar (2 segundos de silencio)
2. Di **"escúchame"** para activarlo (si `WAKE_WORD=1`)
3. Habla tu comando o pregunta
4. Después de cada respuesta quedan 2 turnos sin necesidad de repetir la wake word
5. Di **"salir"** o presiona `Ctrl+C` para cerrar
6. El dashboard está en **http://localhost:5000**

> Si pyautogui se descontrola, mueve el mouse a la **esquina superior izquierda** para abortarlo.

---

## TTS — Opciones de voz

Imai usa TTS en este orden de prioridad:

### 1. Piper TTS (local, sin internet, alta calidad)

```env
PIPER_MODEL=models/es_ES-davefx-medium.onnx
```

Voces disponibles en [rhasspy/piper/releases](https://github.com/rhasspy/piper/releases).

### 2. Edge TTS (requiere internet)

| Código | Descripción |
|--------|-------------|
| `es-CL-LorenzoNeural` | Chile, masculino |
| `es-CL-CatalinaNeural` | Chile, femenino |
| `es-ES-AlvaroNeural` | España, masculino |
| `es-MX-JorgeNeural` | México, masculino |

### 3. pyttsx3 (local, fallback automático)

---

## Estructura del proyecto

```
Imai-IA/
├── Imai.py                     # Loop principal
├── config.py                   # Variables de entorno y constantes
├── requirements.txt
├── .env                        # Claves API (no subir al repo)
├── modules/
│   ├── claude_llm.py           # Claude API: chat, tool calling, visión
│   ├── stt.py                  # Grabación, VAD, transcripción, wake word
│   ├── tts.py                  # Síntesis de voz, barge-in, Piper/Edge/pyttsx3
│   ├── intent.py               # Detección de intención (regex fast path)
│   ├── apps.py                 # Escaneo y apertura/cierre de aplicaciones
│   ├── tools.py                # Volumen, brillo, timers, clima, Spotify, mouse, etc.
│   ├── tools_def.py            # Dispatcher de tool calls de Claude
│   ├── recordatorios.py        # Recordatorios puntuales y recurrentes (APScheduler)
│   ├── calendario.py           # Google Calendar API
│   ├── gmail.py                # Gmail API
│   ├── dashboard.py            # Dashboard web Flask (localhost:5000)
│   ├── urls.py                 # Apertura de sitios y búsquedas web
│   ├── prompt.py               # System prompt dinámico con memoria y fecha
│   ├── memoria.py              # Memoria persistente (JSON + ChromaDB vectorial)
│   ├── historial.py            # Log de conversaciones en formato ChatML
│   ├── rag.py                  # Búsqueda semántica sobre el historial (ChromaDB)
│   └── utils.py                # Utilidades compartidas
├── models/
│   ├── es_ES-davefx-medium.onnx        # Modelo Piper TTS (no subir al repo)
│   ├── es_ES-davefx-medium.onnx.json   # Config Piper TTS
│   └── imai.onnx                       # Modelo wake word personalizado (opcional)
├── data/                       # Archivos de runtime (ignorados por git)
│   ├── memoria.json            # Perfil + hechos del usuario
│   ├── recordatorios.json      # Recordatorios activos
│   ├── apps_cache.json         # Caché de apps instaladas
│   ├── spotify_historial.json  # Historial de canciones
│   ├── calendar_credentials.json  # Credenciales OAuth Google
│   ├── calendar_token.json     # Token Calendar (generado automáticamente)
│   └── gmail_token.json        # Token Gmail (generado automáticamente)
├── historial/                  # Log de conversaciones por día (ignorado por git)
├── chroma_db/                  # Base vectorial ChromaDB (ignorado por git)
├── scripts/
│   └── grabar_wake_word.py     # Graba clips para entrenar el wake word
└── audio/                      # Archivos de audio temporales
```

---

## Wake word

La detección usa Whisper con sliding window (2s, paso 0.5s) y fuzzy matching con rapidfuzz. La wake word por defecto es **"escúchame"** y se configura en `.env`:

```env
WAKE_WORD_TARGET=escuchame
```

Para usar un modelo openWakeWord dedicado, coloca el `.onnx` en `models/` y configura:

```env
WAKE_WORD_MODEL=models/tu_modelo.onnx
```

---

## Memoria

La memoria del usuario se guarda en `data/memoria.json` con dos secciones:

- **Perfil** — datos estructurados: nombre, edad, trabajo, ciudad, etc.
- **Hechos** — datos varios: gustos, rutinas, mascotas, preferencias

Ambas secciones se indexan en ChromaDB para búsqueda semántica. Puedes preguntarle a Imai *"¿qué recuerdas sobre mí?"* y busca por similitud, no solo por coincidencia exacta.

---

## Historial y fine-tuning

Cada conversación se guarda en `historial/YYYY-MM-DD.jsonl` en formato **ChatML**, compatible con [Unsloth](https://github.com/unslothai/unsloth) para fine-tuning QLoRA:

```json
{
  "timestamp": "2026-05-21T21:30:00",
  "messages": [
    {"role": "system", "content": "Eres Imai..."},
    {"role": "user", "content": "¿cuánto es 20% de 350?"},
    {"role": "assistant", "content": "El 20% de 350 es 70."}
  ],
  "intent": "calcular",
  "herramienta": true
}
```

---

## Solución de problemas

**`[ Sin voz detectada ]` constantemente**
Baja `UMBRAL_RMS` en `.env` (ej. `80`).

**Wake word no me detecta**
Desactívalo con `WAKE_WORD=0` y habla directo. O revisa el output `[ Wake word escuchó: '...' ]` para ver qué transcribe Whisper.

**El audio no suena**
ffmpeg no está en el PATH. Configura `FFMPEG_BIN` en `.env`.

**Piper TTS no carga**
Verifica que `PIPER_MODEL` apunte al `.onnx` y que el `.onnx.json` esté en la misma carpeta.

**Claude no responde**
Verifica que `ANTHROPIC_API_KEY` esté en `.env` y que la cuenta tenga crédito.

**Groq STT falla**
Imai cae automáticamente al modelo local faster-whisper.

**Google Calendar / Gmail dan error 403**
Agrega tu email como usuario de prueba en "Pantalla de consentimiento de OAuth" en Google Cloud Console.

**Los recordatorios no suenan**
APScheduler necesita que el proceso siga corriendo. No cierres Imai antes de que llegue la hora.

**pyautogui se descontrola**
Mueve el mouse a la esquina superior izquierda para activar el failsafe y abortar.
