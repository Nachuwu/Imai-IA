"""
Integración con Claude API (Anthropic) para razonamiento y tool calling.
Reemplaza Ollama como LLM en el path de conversación/comandos ambiguos.
"""
import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

_client = None

def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client

# ---------------------------------------------------------------------------
# Herramientas en formato Anthropic
# ---------------------------------------------------------------------------

CLAUDE_TOOLS = [
    {
        "name": "volumen",
        "description": "Controla el volumen del sistema: subir, bajar, silenciar, activar o establecer porcentaje exacto",
        "input_schema": {
            "type": "object",
            "properties": {
                "accion": {"type": "string", "enum": ["subir", "bajar", "silenciar", "activar", "establecer", "consultar"]},
                "pct":    {"type": "integer", "description": "Porcentaje 0-100, solo si accion=establecer"},
            },
            "required": ["accion"],
        },
    },
    {
        "name": "brillo",
        "description": "Controla el brillo de la pantalla",
        "input_schema": {
            "type": "object",
            "properties": {
                "accion": {"type": "string", "enum": ["subir", "bajar", "establecer", "consultar"]},
                "pct":    {"type": "integer", "description": "Porcentaje 0-100, solo si accion=establecer"},
            },
            "required": ["accion"],
        },
    },
    {
        "name": "timer",
        "description": "Crea o cancela un temporizador o alarma",
        "input_schema": {
            "type": "object",
            "properties": {
                "accion":   {"type": "string", "enum": ["crear", "cancelar"]},
                "segundos": {"type": "integer", "description": "Duración en segundos, requerido si accion=crear"},
            },
            "required": ["accion"],
        },
    },
    {
        "name": "spotify",
        "description": "Controla la reproducción de música: siguiente canción, anterior, pausar, parar, o preguntar qué suena",
        "input_schema": {
            "type": "object",
            "properties": {
                "accion": {"type": "string", "enum": ["siguiente", "anterior", "play_pause", "parar", "que_suena"]},
            },
            "required": ["accion"],
        },
    },
    {
        "name": "abrir_app",
        "description": "Abre una aplicación o programa instalado en el sistema",
        "input_schema": {
            "type": "object",
            "properties": {
                "nombre": {"type": "string", "description": "Nombre de la aplicación"},
            },
            "required": ["nombre"],
        },
    },
    {
        "name": "cerrar_app",
        "description": "Cierra una aplicación o programa que está ejecutándose",
        "input_schema": {
            "type": "object",
            "properties": {
                "nombre": {"type": "string", "description": "Nombre de la aplicación"},
            },
            "required": ["nombre"],
        },
    },
    {
        "name": "buscar_archivo",
        "description": "Busca un archivo en el disco duro por nombre",
        "input_schema": {
            "type": "object",
            "properties": {
                "nombre": {"type": "string", "description": "Nombre o parte del nombre del archivo"},
            },
            "required": ["nombre"],
        },
    },
    {
        "name": "hora",
        "description": "Dice la hora actual del sistema",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "fecha",
        "description": "Dice la fecha de hoy",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "clima",
        "description": "Consulta el clima actual de una ciudad",
        "input_schema": {
            "type": "object",
            "properties": {
                "ciudad": {"type": "string", "description": "Nombre de la ciudad"},
            },
            "required": ["ciudad"],
        },
    },
    {
        "name": "calcular",
        "description": "Calcula una expresión matemática",
        "input_schema": {
            "type": "object",
            "properties": {
                "expresion": {"type": "string", "description": "Expresión a calcular, ej: '20% de 350'"},
            },
            "required": ["expresion"],
        },
    },
    {
        "name": "portapapeles",
        "description": "Lee el contenido actual del portapapeles",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "captura_pantalla",
        "description": "Toma una captura de pantalla y la guarda",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "abrir_sitio",
        "description": "Abre un sitio web conocido: youtube, google, gmail, github, netflix, spotify, twitch, reddit, instagram, facebook, whatsapp, wikipedia, twitter",
        "input_schema": {
            "type": "object",
            "properties": {
                "sitio": {"type": "string", "description": "Nombre del sitio"},
            },
            "required": ["sitio"],
        },
    },
    {
        "name": "buscar_youtube",
        "description": "Busca y abre un video o canción en YouTube",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Lo que se quiere buscar o reproducir"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "buscar_google",
        "description": "Busca algo en Google",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Término de búsqueda"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "guardar_memoria",
        "description": "Guarda un hecho, preferencia o dato misceláneo del usuario. Para datos estructurados del perfil (nombre, edad, trabajo, ciudad, etc.) usa guardar_perfil en su lugar.",
        "input_schema": {
            "type": "object",
            "properties": {
                "hecho": {"type": "string", "description": "El hecho a recordar"},
            },
            "required": ["hecho"],
        },
    },
    {
        "name": "guardar_perfil",
        "description": "Guarda un campo estructurado del perfil del usuario: nombre, edad, trabajo, ciudad, idioma, mascota u otros datos personales clave.",
        "input_schema": {
            "type": "object",
            "properties": {
                "campo": {"type": "string", "description": "Nombre del campo, ej: 'nombre', 'edad', 'trabajo', 'ciudad'"},
                "valor": {"type": "string", "description": "Valor del campo"},
            },
            "required": ["campo", "valor"],
        },
    },
    {
        "name": "crear_proyecto",
        "description": "Registra un nuevo proyecto en el que el usuario está trabajando, con su estado inicial.",
        "input_schema": {
            "type": "object",
            "properties": {
                "nombre": {"type": "string", "description": "Nombre del proyecto"},
                "estado": {"type": "string", "description": "Estado inicial, ej: 'en curso', 'planeando', 'pausado'"},
                "notas":  {"type": "string", "description": "Notas adicionales sobre el proyecto"},
            },
            "required": ["nombre"],
        },
    },
    {
        "name": "actualizar_proyecto",
        "description": "Actualiza el estado, última acción o notas de un proyecto ya registrado. Si el proyecto no existe, lo crea. Úsala cuando el usuario cuente avances o cambios de estado de algo en lo que está trabajando.",
        "input_schema": {
            "type": "object",
            "properties": {
                "nombre":        {"type": "string", "description": "Nombre del proyecto a actualizar"},
                "estado":        {"type": "string", "description": "Nuevo estado, ej: 'en curso', 'pausado', 'terminado'"},
                "ultima_accion": {"type": "string", "description": "Última acción o avance realizado en el proyecto"},
                "notas":         {"type": "string", "description": "Notas adicionales"},
            },
            "required": ["nombre"],
        },
    },
    {
        "name": "listar_proyectos",
        "description": "Muestra todos los proyectos registrados con su estado y última acción. Úsala cuando el usuario pregunte en qué está trabajando o cómo van sus proyectos.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "eliminar_proyecto",
        "description": "Elimina un proyecto del seguimiento, por ejemplo cuando ya está completamente terminado y archivado.",
        "input_schema": {
            "type": "object",
            "properties": {
                "nombre": {"type": "string", "description": "Nombre del proyecto a eliminar"},
            },
            "required": ["nombre"],
        },
    },
    {
        "name": "no_molestar",
        "description": "Desactiva el micrófono temporalmente por un tiempo determinado",
        "input_schema": {
            "type": "object",
            "properties": {
                "segundos": {"type": "integer", "description": "Duración en segundos"},
            },
            "required": ["segundos"],
        },
    },
    {
        "name": "ventana",
        "description": "Controla ventanas abiertas en el escritorio: minimizar, maximizar, restaurar, enfocar (traer al frente) o listar todas las ventanas.",
        "input_schema": {
            "type": "object",
            "properties": {
                "accion": {"type": "string", "enum": ["minimizar", "maximizar", "restaurar", "enfocar", "listar"]},
                "titulo": {"type": "string", "description": "Título o parte del título de la ventana"},
            },
            "required": ["accion"],
        },
    },
    {
        "name": "recordatorio",
        "description": "Programa un recordatorio para una fecha y hora específica. Convierte la fecha natural al formato YYYY-MM-DD HH:MM usando la fecha actual del sistema.",
        "input_schema": {
            "type": "object",
            "properties": {
                "mensaje": {"type": "string", "description": "El mensaje del recordatorio"},
                "cuando":  {"type": "string", "description": "Fecha y hora en formato YYYY-MM-DD HH:MM"},
            },
            "required": ["mensaje", "cuando"],
        },
    },
    {
        "name": "listar_recordatorios",
        "description": "Muestra todos los recordatorios pendientes",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "cancelar_recordatorio",
        "description": "Cancela el último recordatorio programado",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "control_pc",
        "description": "Controla el estado del PC: apagar, reiniciar, bloquear pantalla, suspender o cancelar un apagado en curso",
        "input_schema": {
            "type": "object",
            "properties": {
                "accion": {"type": "string", "enum": ["apagar", "reiniciar", "bloquear", "suspender", "cancelar_apagado"]},
            },
            "required": ["accion"],
        },
    },
    {
        "name": "actualizar_memoria",
        "description": "Actualiza un dato ya guardado del usuario (edad, ciudad, trabajo, etc.). Úsalo cuando el usuario corrija o cambie algo que ya estaba anotado.",
        "input_schema": {
            "type": "object",
            "properties": {
                "hecho_nuevo": {"type": "string", "description": "El dato actualizado"},
                "patron":      {"type": "string", "description": "Palabra clave del dato a reemplazar, ej: 'edad', 'ciudad', 'trabajo'"},
            },
            "required": ["hecho_nuevo"],
        },
    },
    {
        "name": "buscar_web",
        "description": "Busca información en internet y devuelve una respuesta directa. Úsala para preguntas de conocimiento general, datos, definiciones, noticias, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Lo que se quiere buscar"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "analizar_pantalla",
        "description": "Toma una captura de pantalla y la analiza con IA. Úsala cuando el usuario pregunte qué hay en pantalla, qué dice un texto, analiza un error, describe lo que ves, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pregunta": {"type": "string", "description": "La pregunta específica sobre la pantalla"},
            },
            "required": ["pregunta"],
        },
    },
    {
        "name": "ver_camara",
        "description": "Captura un frame de la webcam y analiza a la persona frente a ella. Úsalo cuando el usuario pregunte sobre sí mismo: '¿cómo estoy?', '¿parezco cansado?', '¿qué ropa tengo?', '¿qué cara estoy poniendo?'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pregunta": {"type": "string", "description": "Qué quieres saber sobre la persona"},
            },
            "required": ["pregunta"],
        },
    },
    {
        "name": "describir_entorno",
        "description": "Captura un frame de la webcam y analiza el entorno físico. Úsalo cuando el usuario pregunte sobre su alrededor: '¿qué hay en mi escritorio?', '¿qué ves detrás de mí?', '¿cómo está la habitación?'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pregunta": {"type": "string", "description": "Qué quieres saber sobre el entorno"},
            },
            "required": ["pregunta"],
        },
    },
    {
        "name": "control_input",
        "description": "Controla el mouse y teclado: escribir texto, presionar teclas, hacer scroll, hacer clic en coordenadas o buscar y hacer clic en un elemento de la pantalla por su texto.",
        "input_schema": {
            "type": "object",
            "properties": {
                "accion":    {"type": "string", "enum": ["escribir", "tecla", "scroll", "click", "click_texto"]},
                "texto":     {"type": "string", "description": "Texto a escribir, o nombre del elemento a buscar en pantalla"},
                "combo":     {"type": "string", "description": "Tecla o combinación: 'enter', 'ctrl+c', 'alt+f4', etc."},
                "direccion": {"type": "string", "enum": ["arriba", "abajo"], "description": "Dirección del scroll"},
                "cantidad":  {"type": "integer", "description": "Líneas de scroll"},
                "x":         {"type": "integer", "description": "Coordenada X para click"},
                "y":         {"type": "integer", "description": "Coordenada Y para click"},
            },
            "required": ["accion"],
        },
    },
    {
        "name": "leer_correos",
        "description": "Lee los últimos correos de Gmail",
        "input_schema": {
            "type": "object",
            "properties": {
                "n": {"type": "integer", "description": "Cantidad de correos a leer (default 5)"},
            },
        },
    },
    {
        "name": "enviar_correo",
        "description": "Envía un correo por Gmail",
        "input_schema": {
            "type": "object",
            "properties": {
                "destinatario": {"type": "string", "description": "Dirección de email del destinatario"},
                "asunto":       {"type": "string", "description": "Asunto del correo"},
                "cuerpo":       {"type": "string", "description": "Cuerpo del mensaje"},
            },
            "required": ["destinatario", "asunto", "cuerpo"],
        },
    },
    {
        "name": "buscar_memoria",
        "description": "Busca en la memoria del usuario de forma semántica. Úsala cuando el usuario pregunte por algo que Imai debería recordar sobre él.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Lo que se quiere buscar en la memoria"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "historial_spotify",
        "description": "Muestra las canciones escuchadas recientemente en Spotify",
        "input_schema": {
            "type": "object",
            "properties": {
                "n": {"type": "integer", "description": "Cantidad de canciones a mostrar (default 10)"},
            },
        },
    },
    {
        "name": "alarma_recurrente",
        "description": "Crea una alarma que se repite: todos los días, un día de la semana, entre semana o fines de semana.",
        "input_schema": {
            "type": "object",
            "properties": {
                "mensaje":    {"type": "string", "description": "Qué decir cuando suene la alarma"},
                "hora":       {"type": "string", "description": "Hora en formato HH:MM"},
                "frecuencia": {"type": "string", "enum": [
                    "diario", "entre_semana", "fines_de_semana",
                    "lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"
                ]},
            },
            "required": ["mensaje", "hora", "frecuencia"],
        },
    },
    {
        "name": "calendario_hoy",
        "description": "Muestra los eventos de Google Calendar para hoy",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "crear_evento",
        "description": "Crea un evento en Google Calendar. Convierte la fecha y hora natural al formato YYYY-MM-DD HH:MM.",
        "input_schema": {
            "type": "object",
            "properties": {
                "titulo":       {"type": "string", "description": "Nombre o título del evento"},
                "cuando":       {"type": "string", "description": "Fecha y hora en formato YYYY-MM-DD HH:MM"},
                "duracion_min": {"type": "integer", "description": "Duración en minutos (default 60)"},
            },
            "required": ["titulo", "cuando"],
        },
    },
    {
        "name": "leer_url",
        "description": "Lee y resume el contenido de una página web, o responde una pregunta específica sobre su contenido. Úsalo cuando el usuario diga 'léeme esto', 'resume esta página', 'qué dice aquí', 'de qué trata esto', 'explícame la sección de X'. Si Chrome, Edge o Firefox está activo, captura la URL automáticamente.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url":      {"type": "string", "description": "URL completa a leer. Si se omite, se captura del navegador activo."},
                "pregunta": {"type": "string", "description": "Pregunta específica sobre el contenido, ej: 'explícame los precios' o 'cuál es la conclusión'. Si se omite, resume el artículo."},
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Consulta principal
# ---------------------------------------------------------------------------

def consultar(historial, hablar_cb=None):
    """
    Consulta a Claude con streaming y tool calling.
    historial: lista con system + mensajes en formato {"role", "content"}.
    Retorna (texto_respuesta, tool_calls).
    """
    client = _get_client()

    system_msg = ""
    messages   = []
    for msg in historial:
        if msg["role"] == "system":
            system_msg = msg["content"]
        else:
            messages.append({"role": msg["role"], "content": msg["content"]})

    texto      = ""
    tool_calls = []
    buffer     = ""

    with client.messages.stream(
        model=CLAUDE_MODEL,
        max_tokens=300,
        system=system_msg,
        tools=CLAUDE_TOOLS,
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            texto  += text
            buffer += text
            print(text, end="", flush=True)

            if hablar_cb:
                while True:
                    for sep in ('.', '!', '?'):
                        idx = buffer.find(sep)
                        if idx != -1:
                            oracion = buffer[:idx + 1].strip()
                            buffer  = buffer[idx + 1:]
                            if oracion:
                                hablar_cb(oracion)
                            break
                    else:
                        break

        final = stream.get_final_message()

    print()

    if hablar_cb and buffer.strip():
        hablar_cb(buffer.strip())

    for block in final.content:
        if block.type == "tool_use":
            tool_calls.append({
                "function": {
                    "name":      block.name,
                    "arguments": block.input,
                }
            })

    return texto, tool_calls


def analizar_imagen(ruta, pregunta="¿Qué hay en esta imagen?"):
    """Envía una imagen a Claude y devuelve su análisis en texto."""
    import base64
    client = _get_client()
    with open(ruta, "rb") as f:
        datos = base64.standard_b64encode(f.read()).decode("utf-8")
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=300,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/png", "data": datos},
                },
                {"type": "text", "text": pregunta + " Responde en español, conciso, sin markdown."},
            ],
        }],
    )
    return response.content[0].text
