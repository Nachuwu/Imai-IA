import unicodedata

def sin_acentos(texto):
    return unicodedata.normalize("NFD", texto).encode("ascii", "ignore").decode()
