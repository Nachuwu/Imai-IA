# Imai — Asistente de voz personal

Imai es un asistente personal de voz en español que corre en tu máquina. Escucha tu micrófono, transcribe lo que dices, ejecuta comandos directos o consulta un modelo de lenguaje local, y te responde en voz alta.

Su nombre viene de **Imai**, la estrella delta de la Cruz del Sur, visible desde Chile.

---

## Qué puede hacer

### Control del sistema
| Comando | Ejemplo |
|---------|---------|
| Volumen | "sube el volumen", "pon el volumen al 40", "silencia" |
| Brillo | "sube el brillo", "pon el brillo al 60" |
| Aplicaciones | "abre chrome", "cierra spotify" |
| Captura de pantalla | "toma una captura de pantalla" |
| Portapapeles | "¿qué tengo copiado?" |

### Música y medios
| Comando | Ejemplo |
|---------|---------|
| Spotify | "siguiente canción", "pausa la música", "¿qué está sonando?" |
| YouTube | "pon una canción de Bad Bunny en YouTube" |
| Sitios web | "abre GitHub", "busca recetas en Google" |

### Información
| Comando | Ejemplo |
|---------|---------|
| Hora y fecha | "¿qué hora es?", "¿qué día es hoy?" |
| Clima | "¿cómo está el clima en Santiago?" |
| Calculadora | "¿cuánto es 20% de 350?", "calcula 8 por 7 menos 3" |

### Organización
| Comando | Ejemplo |
|---------|---------|
| Timers | "pon un timer de 2 minutos", "avísame en media hora" |
| Cancelar timer | "cancela el timer" |
| Buscar archivos | "busca el archivo presupuesto" |
| Modo no molestar | "silencio por 10 minutos" |

### Memoria y contexto
| Función | Ejemplo |
|---------|---------|
| Memoria persistente | "recuerda que me llamo Ignacio" |
| Historial con RAG | "¿recuerdas lo que hablamos ayer?" |

### Comandos encadenados
```
"sube el volumen y abre chrome"
"pon el volumen al 50 y pausa la música"
```

---

## Arquitectura

```
Micrófono → Wake word → STT → Intención → Herramienta O LLM → TTS → Parlante
```

| Componente | Tecnología |
|------------|------------|
| Wake word | faster-whisper (detección de "Imai") |
| STT | Groq Whisper (`whisper-large-v3`) + faster-whisper local como fallback |
| Detección de intención | Regex + LLM fallback |
| LLM | Ollama (`gemma3:4b` recomendado) |
| TTS | Piper TTS (local) → Edge TTS (nube) → pyttsx3 (fallback) |
| Memoria | `memoria.json` inyectado al system prompt |
| Historial | JSONL por día en formato ChatML (compatible con fine-tuning Unsloth/QLoRA) |
| RAG | ChromaDB + sentence-transformers |

---

## Requisitos previos

- Python 3.10 o superior
- [Ollama](https://ollama.com) instalado y corriendo
- [ffmpeg](https://www.gyan.dev/ffmpeg/builds/) instalado

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

# Windows
venv\Scripts\activate

pip install -r requirements.txt
```

### 3. Instalar el modelo de lenguaje

```bash
ollama pull gemma3:4b
```

> Puedes usar cualquier modelo de [ollama.com/library](https://ollama.com/library). Se configura con `MODEL=` en `.env`.

### 4. Configurar el entorno

Crea un archivo `.env` en la raíz del proyecto:

```env
# Modelo de lenguaje (debe estar descargado en Ollama)
MODEL=gemma3:4b

# STT — Groq API para Whisper en la nube (opcional pero recomendado)
GROQ_API_KEY=tu_api_key_aqui

# Voz de Edge TTS (si no usas Piper)
VOZ=es-CL-LorenzoNeural

# Ciudad por defecto para el clima
CIUDAD=Santiago

# Wake word: "1" activa, "0" desactiva
WAKE_WORD=1

# Ruta a ffmpeg/bin (solo si no está en el PATH)
FFMPEG_BIN=C:\ruta\a\ffmpeg\bin

# Piper TTS local (opcional — ver sección de TTS)
PIPER_MODEL=

# Sensibilidad del micrófono
UMBRAL_RMS=150
SILENCIO_MAX=1.5
DURACION_MAX=15
```

---

## Uso

```bash
python Imai.py
```

1. Imai calibra el micrófono automáticamente al arrancar (2 segundos de silencio)
2. Di **"Imai"** para activarlo (si `WAKE_WORD=1`)
3. Habla tu comando o pregunta
4. Imai responde en voz — di **"detente"**, **"basta"** o **"para"** para interrumpirlo
5. Di **"salir"** o presiona `Ctrl+C` para cerrar

---

## TTS — Opciones de voz

Imai usa TTS en este orden de prioridad:

### 1. Piper TTS (local, sin internet, alta calidad)

```bash
pip install piper-tts
```

Descarga un modelo español desde [rhasspy/piper/releases](https://github.com/rhasspy/piper/releases) (ej. `es_ES-davefx-medium.onnx`) y configura en `.env`:

```env
PIPER_MODEL=C:\ruta\al\modelo\es_ES-davefx-medium.onnx
```

### 2. Edge TTS (requiere internet)

Funciona sin configuración adicional si ffplay está instalado.

| Código | Descripción |
|--------|-------------|
| `es-CL-LorenzoNeural` | Chile, masculino |
| `es-CL-CatalinaNeural` | Chile, femenino |
| `es-ES-AlvaroNeural` | España, masculino |
| `es-MX-JorgeNeural` | México, masculino |

### 3. pyttsx3 (local, fallback automático si Edge TTS falla)

---

## Estructura del proyecto

```
Imai-IA/
├── Imai.py                 # Loop principal
├── config.py               # Variables de entorno y constantes
├── requirements.txt        # Dependencias Python
├── modules/
│   ├── stt.py              # Grabación, VAD, transcripción, wake word
│   ├── tts.py              # Síntesis de voz, barge-in, Piper/Edge/pyttsx3
│   ├── intent.py           # Detección de intención (regex + LLM fallback)
│   ├── apps.py             # Escaneo y apertura/cierre de aplicaciones
│   ├── tools.py            # Volumen, brillo, timers, clima, calculadora, etc.
│   ├── urls.py             # Apertura de sitios y búsquedas web
│   ├── prompt.py           # System prompt con memoria inyectada
│   ├── memoria.py          # Memoria persistente entre sesiones
│   ├── historial.py        # Log de conversaciones en formato ChatML
│   ├── rag.py              # Búsqueda semántica sobre el historial (ChromaDB)
│   └── utils.py            # Utilidades compartidas
├── historial/              # JSONL por día (ignorado por git)
├── chroma_db/              # Base de datos vectorial (ignorado por git)
└── audio/                  # Archivos de audio temporales
```

---

## Historial y fine-tuning

Cada conversación se guarda en `historial/YYYY-MM-DD.jsonl` en formato **ChatML**, compatible directo con [Unsloth](https://github.com/unslothai/unsloth) para fine-tuning QLoRA:

```json
{
  "timestamp": "2026-05-15T21:30:00",
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
Desactívalo con `WAKE_WORD=0` en `.env` y habla directo.

**El audio no suena**
ffmpeg no está en el PATH. Configura `FFMPEG_BIN` en `.env`.

**Ollama no responde**
Ejecuta `ollama serve` y verifica que el modelo esté descargado con `ollama list`.

**Groq STT falla**
Imai cae automáticamente al modelo local. Verifica tu `GROQ_API_KEY`.
