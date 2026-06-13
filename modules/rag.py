import re
import json
import os
import glob
import logging
import chromadb
from sentence_transformers import SentenceTransformer

_log = logging.getLogger(__name__)

_PATRONES_HISTORIAL = [
    r"\b(recuerdas|recuerda|acordas|dijiste|dije|hablamos|conversamos)\b",
    r"\b(antes|ayer|la semana pasada|anteriormente|la vez que)\b",
    r"\b(qu[eé] (te pregunte|me dijiste|hablamos|conversamos))\b",
    r"\b([uú]ltima vez|[uú]ltima conversaci[oó]n|[uú]ltima sesi[oó]n)\b",
    r"\b(en qu[eé] quedamos|qu[eé] acordamos)\b",
]

def es_consulta_historial(texto):
    txt = texto.lower()
    return any(re.search(p, txt) for p in _PATRONES_HISTORIAL)

_CARPETA = os.path.join(os.path.dirname(__file__), "..", "historial")
_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "chroma_db")
_MODELO  = "paraphrase-multilingual-MiniLM-L12-v2"

_client = chromadb.PersistentClient(path=_DB_PATH)
_col    = _client.get_or_create_collection("historial_imai")
_emb    = SentenceTransformer(_MODELO)

def indexar_historial():
    archivos      = glob.glob(os.path.join(_CARPETA, "*.jsonl"))
    ids_existentes = set(_col.get()["ids"])
    nuevos        = 0

    for archivo in archivos:
        with open(archivo, encoding="utf-8") as f:
            for i, linea in enumerate(f):
                try:
                    entrada = json.loads(linea)
                except json.JSONDecodeError:
                    continue
                doc_id = f"{os.path.basename(archivo)}_{i}"
                if doc_id in ids_existentes:
                    continue
                msgs  = entrada.get("messages", [])
                texto = " ".join(
                    m["content"] for m in msgs
                    if m["role"] in ("user", "assistant") and m.get("content")
                )
                if not texto.strip():
                    continue
                _col.add(
                    ids=[doc_id],
                    documents=[texto],
                    metadatas=[{
                        "timestamp": entrada.get("timestamp", ""),
                        "intent":    entrada.get("intent", ""),
                    }],
                )
                nuevos += 1

    _log.info("RAG: %d entradas nuevas indexadas.", nuevos)

def buscar(query, n=3):
    total = _col.count()
    if total == 0:
        return []
    resultados = _col.query(
        query_texts=[query],
        n_results=min(n, total),
    )
    return resultados["documents"][0]
