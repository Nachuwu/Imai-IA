import re
import shutil
import subprocess
import webbrowser

_SITIOS = {
    "youtube":   "https://www.youtube.com",
    "google":    "https://www.google.com",
    "gmail":     "https://mail.google.com",
    "twitter":   "https://www.twitter.com",
    "instagram": "https://www.instagram.com",
    "facebook":  "https://www.facebook.com",
    "whatsapp":  "https://web.whatsapp.com",
    "netflix":   "https://www.netflix.com",
    "spotify":   "https://open.spotify.com",
    "twitch":    "https://www.twitch.tv",
    "reddit":    "https://www.reddit.com",
    "github":    "https://www.github.com",
    "wikipedia": "https://www.wikipedia.org",
}

def _abrir_primer_resultado_yt(query):
    """Abre el primer video de YouTube para la búsqueda dada. Requiere yt-dlp."""
    if shutil.which("yt-dlp"):
        try:
            r = subprocess.run(
                ["yt-dlp", f"ytsearch1:{query}", "--get-id", "--no-playlist"],
                capture_output=True, text=True, timeout=10,
            )
            video_id = r.stdout.strip().splitlines()[0] if r.stdout.strip() else None
            if video_id:
                webbrowser.open(f"https://www.youtube.com/watch?v={video_id}")
                return True
        except Exception:
            pass
    # fallback: página de búsqueda
    webbrowser.open(f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}")
    return False

def manejar(texto):
    txt = texto.lower()

    # "pon/reproduce/toca X en YouTube"
    m = re.search(r'(?:pone?|reproduce|toca|ponme|reproducir|quiero escuchar|escuchar)\s+(.+?)\s+en\s+youtube', txt)
    if m:
        q = m.group(1).strip()
        directo = _abrir_primer_resultado_yt(q)
        return f"Reproduciendo {q} en YouTube." if directo else f"Buscando {q} en YouTube."

    m = re.search(r'busca\s+(.+?)\s+en\s+youtube', txt)
    if m:
        q = m.group(1).strip()
        webbrowser.open(f"https://www.youtube.com/results?search_query={q.replace(' ', '+')}")
        return f"Buscando {q} en YouTube."

    m = re.search(r'busca\s+(.+?)\s+en\s+(google|internet)', txt)
    if m:
        q = m.group(1).strip()
        webbrowser.open(f"https://www.google.com/search?q={q.replace(' ', '+')}")
        return f"Buscando {q} en Google."

    for sitio, url in _SITIOS.items():
        if sitio in txt:
            webbrowser.open(url)
            return f"Abriendo {sitio}."

    # Intento como URL directa
    candidato = re.sub(r'\b(abre|abrir|ir a|entra a)\b', '', txt).strip()
    if candidato:
        webbrowser.open(f"https://{candidato}" if not candidato.startswith("http") else candidato)
        return f"Abriendo {candidato}."

    return "No supe qué abrir."
