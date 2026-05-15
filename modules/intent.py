import re
import ollama
from config import MODEL
from modules.utils import sin_acentos as _sin_acentos

# ---------------------------------------------------------------------------
# Números en español → entero
# ---------------------------------------------------------------------------

_NUMEROS_ES = {
    "un": 1, "una": 1, "uno": 1,
    "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
    "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
    "dieciseis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19,
    "veinte": 20, "veintiun": 21, "veintidos": 22, "veintitres": 23,
    "veinticuatro": 24, "veinticinco": 25, "veintiseis": 26,
    "veintisiete": 27, "veintiocho": 28, "veintinueve": 29,
    "treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60,
}

def _parse_num(token):
    """Convierte un token a entero: dígitos o palabra española."""
    if token.isdigit():
        return int(token)
    clave = _sin_acentos(token.lower())
    return _NUMEROS_ES.get(clave)

def _buscar_numero(texto, unidad):
    """Extrae el número antes de `unidad` en el texto (dígito o palabra)."""
    patron = rf"(\d+|[a-záéíóúüñ]+)\s*{unidad}"
    m = re.search(patron, _sin_acentos(texto), re.IGNORECASE)
    if m:
        return _parse_num(m.group(1))
    return None

# ---------------------------------------------------------------------------
# Patrones de palabras clave — se evalúan primero, sin tocar el LLM
# ---------------------------------------------------------------------------

_NUMEROS_PAT = r"(\d+|un[oa]?|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|" \
               r"once|doce|trece|catorce|quince|veinte|treinta|cuarenta|cincuenta|media)"

_PATRONES = {
    "hora":         r"\b(qu[eé] hora|la hora|d[ií]me la hora|qu[eé] hora es)\b",
    "fecha":        r"\b(qu[eé] d[ií]a|qu[eé] fecha|hoy es|d[ií]a es hoy|fecha de hoy)\b",
    "clima":        r"\b(clima|tiempo en|temperatura|llueve|lluvia|nublado|c[oó]mo est[aá] el tiempo|c[oó]mo est[aá] el clima)\b",
    "calcular":     r"\b(cu[aá]nto (es|da|son|vale)|calcula(me)?|cu[aá]nto es|\d+\s*[+\-*/%]\s*\d+)\b",
    "portapapeles": r"\b(portapapeles|qu[eé] tengo copiado|lee el portapapeles|qu[eé] hay copiado)\b",
    "captura":      r"\b(captura|screenshot|toma (una )?foto de pantalla|foto de pantalla)\b",
    "spotify":      r"\b(siguiente (canci[oó]n|tema)|canci[oó]n anterior|pausa (la )?m[uú]sica|"
                    r"reanuda|parar (la )?m[uú]sica|qu[eé] (canci[oó]n|est[aá] sonando|suena)|"
                    r"siguiente tema|tema anterior)\b",
    "brillo":       r"\b(brillo|m[aá]s (claro|oscuro)|sube (el )?brillo|baja (el )?brillo)\b",
    "url":          r"\b(abre (youtube|google|gmail|twitter|instagram|facebook|whatsapp|netflix|"
                    r"spotify web|twitch|reddit|github|wikipedia)|"
                    r"busca .{1,40} en (google|youtube|internet)|"
                    r"(pone?|reproduce|toca|ponme|reproducir).{1,50} en youtube|"
                    r"(quiero escuchar|escuchar).{1,50} en youtube)\b",
    "no_molestar":  r"\b(no molestar|modo silencio|silencio por|desactiva (el )?micro|para de escuchar)\b",
    "cancelar_timer": r"\b(cancela|cancelar|para|detener|quitar)\b.{0,20}\b(timer|alarma|cronometro)\b",
    "memoria": r"\b(recuerda|anota|guarda|ten en cuenta|sab[eé]s que|nota que)\b",
    "timer":  rf"\b(timer|alarma|cronometro|av[íi]same|recu[eé]rdame|"
              rf"pon(me)? un (timer|alarma)|crea(me)? (un )?(timer)|"
              rf"{_NUMEROS_PAT}\s*(minutos?|segundos?|horas?))\b",
    "abrir":  r"\b(abre|abrir|inicia|lanza|ejecuta)\b",
    "cerrar": r"\b(cierra|cerrar|mata|termina|sal de)\b",
    "volumen": r"\b(volumen|sube (el )?volumen|baja (el )?volumen|silencia|silencio|"
               r"sin sonido|activa (el )?sonido|pon(lo|la)? (al|en) \d+)\b",
    "buscar": r"\b(busca|encuentra|d[oó]nde est[aá]|buscar archivo|busca el|busca la)\b",
}

# Palabras a ignorar al extraer el objeto de la frase
_STOPWORDS = {
    "el", "la", "los", "las", "un", "una", "unos", "unas",
    "me", "por", "favor", "porfavor",
    "abre", "abrir", "inicia", "lanza", "ejecuta", "pon",
    "cierra", "cerrar", "mata", "termina", "sal",
    "volumen", "timer", "alarma", "busca", "encuentra",
    "de", "del", "al", "a", "y", "o", "que", "con",
    "aplicacion", "aplicaciones", "programa", "programas", "app",
}

_INTENTS_VALIDOS = set(_PATRONES.keys()) | {"ninguna", "cancelar_timer", "memoria"}


def detectar(texto):
    """
    Retorna (intent, objeto) donde intent es una de las claves de _PATRONES
    (o 'ninguna') y objeto es la palabra/frase relevante extraída del texto.
    """
    txt = texto.lower().strip()

    for intent, patron in _PATRONES.items():
        if re.search(patron, txt, re.IGNORECASE):
            return intent, _extraer_objeto(txt, intent)

    # Fallback al LLM solo si ningún patrón coincidió
    intent = _intent_llm(texto)
    return intent, _extraer_objeto(txt, intent)


def _extraer_objeto(texto, intent):
    """Extrae la palabra clave relevante (app, nivel de volumen, segundos, etc.)."""

    if intent == "volumen":
        m = re.search(r"\b(\d+)\s*(%|por ciento)?", texto)
        if m:
            return int(m.group(1))
        if re.search(r"\b(sube|m[aá]s alto|aumenta)\b", texto):
            return "subir"
        if re.search(r"\b(baja|m[aá]s bajo|disminuye)\b", texto):
            return "bajar"
        if re.search(r"\b(silencia|mute|sin sonido)\b", texto):
            return "silenciar"
        if re.search(r"\b(activa|dessilencia|con sonido)\b", texto):
            return "activar"
        return None

    if intent == "timer":
        segundos = 0
        if "media hora" in _sin_acentos(texto):
            segundos += 1800
        else:
            n = _buscar_numero(texto, "hora")
            if n:
                segundos += n * 3600
        n = _buscar_numero(texto, "minuto")
        if n:
            segundos += n * 60
        n = _buscar_numero(texto, "segundo")
        if n:
            segundos += n
        return segundos if segundos else None

    if intent == "clima":
        m = re.search(r'\ben\s+([A-Za-záéíóúñü][a-záéíóúñü\s]{2,20})', texto, re.IGNORECASE)
        return m.group(1).strip() if m else None

    if intent == "calcular":
        exp = re.sub(r'\b(cu[aá]nto (es|da|son|vale)|calcula(me)?|qu[eé] es|resultado de)\b', '', texto)
        return exp.strip("?¿ ") or None

    if intent in ("hora", "fecha", "portapapeles", "captura"):
        return None

    if intent == "spotify":
        if re.search(r'\b(siguiente|pr[oó]xima)\b', texto):   return "siguiente"
        if re.search(r'\b(anterior|atr[aá]s|volver)\b', texto): return "anterior"
        if re.search(r'\b(pausa|pausar)\b', texto):            return "pausa"
        if re.search(r'\b(parar|detener|stop)\b', texto):     return "parar"
        if re.search(r'\b(qu[eé]|cu[aá]l).*(canci[oó]n|suena|sonando)\b', texto): return "que_suena"
        return "play_pause"

    if intent == "brillo":
        m = re.search(r'\b(\d+)\b', texto)
        if m: return int(m.group(1))
        if re.search(r'\b(sube|m[aá]s claro|aumenta)\b', texto): return "subir"
        if re.search(r'\b(baja|m[aá]s oscuro|disminuye)\b', texto): return "bajar"
        return None

    if intent == "url":
        return texto  # manejar() en urls.py parsea el texto completo

    if intent == "no_molestar":
        return _extraer_objeto(texto, "timer")  # reutiliza el parser de duración

    if intent in ("abrir", "cerrar", "buscar"):
        palabras = _sin_acentos(texto).split()
        objeto = " ".join(p.strip(".,;:!?") for p in palabras
                          if p.strip(".,;:!?") not in _STOPWORDS)
        return objeto.strip() or None

    return None


def _intent_llm(texto):
    """Consulta al LLM solo cuando los patrones no matchean nada."""
    prompt = (
        f"Clasifica esta instrucción en una sola palabra: "
        f"abrir, cerrar, volumen, timer, buscar, o ninguna.\n"
        f"Instrucción: {texto}\n"
        f"Responde solo la palabra, sin explicación."
    )
    try:
        r = ollama.chat(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"num_predict": 5},
        )
        respuesta = r["message"]["content"].strip().lower()
        # Extraer solo la primera palabra válida de la respuesta
        for palabra in respuesta.split():
            if palabra in _INTENTS_VALIDOS:
                return palabra
    except Exception:
        pass
    return "ninguna"
