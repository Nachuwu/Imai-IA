"""
Detecta la aplicación activa y extrae contexto útil del título de la ventana.
"""
import pygetwindow as gw

_APPS = {
    "visual studio code": "VSCode",
    " - code":            "VSCode",
    "google chrome":      "Chrome",
    "mozilla firefox":    "Firefox",
    "microsoft edge":     "Edge",
    "opera":              "Opera",
    "brave":              "Brave",
    "spotify":            "Spotify",
    "discord":            "Discord",
    "whatsapp":           "WhatsApp",
    "telegram":           "Telegram",
    "notepad":            "Bloc de notas",
    "excel":              "Excel",
    "word":               "Word",
    "powerpoint":         "PowerPoint",
    "explorer":           "Explorador de archivos",
    "obs":                "OBS Studio",
    "steam":              "Steam",
}

_NAVEGADORES = {"Chrome", "Firefox", "Edge", "Opera", "Brave"}
_EDITORES    = {"VSCode"}


def get_app_activa() -> str | None:
    """
    Retorna una string de contexto como:
      'Chrome: ¿Qué es la fusión nuclear? - Wikipedia'
      'VSCode: main.py'
      'Spotify'
    Retorna None si no se pudo detectar o la ventana no tiene título.
    """
    try:
        win = gw.getActiveWindow()
        if not win or not win.title.strip():
            return None

        titulo       = win.title.strip()
        titulo_lower = titulo.lower()

        for clave, nombre in _APPS.items():
            if clave in titulo_lower:
                if nombre in _NAVEGADORES:
                    # "Título de página - Google Chrome" → "Chrome: Título de página"
                    partes = titulo.rsplit(" - ", 1)
                    pagina = partes[0].strip() if len(partes) > 1 else titulo
                    return f"{nombre}: {pagina[:80]}"

                if nombre in _EDITORES:
                    # "archivo.py - proyecto - Visual Studio Code" → "VSCode: archivo.py"
                    partes = titulo.split(" - ")
                    archivo = partes[0].strip() if partes else titulo
                    return f"{nombre}: {archivo[:60]}"

                return nombre

        # App desconocida — devuelve el título recortado
        return titulo[:60] if titulo else None

    except Exception:
        return None
