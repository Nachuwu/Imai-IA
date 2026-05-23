"""
Dashboard web local — http://localhost:5000
Muestra memoria, historial y recordatorios en tiempo real.
"""
import json
import os
import glob
import threading
import time
import cv2
from flask import Flask, jsonify, render_template_string, Response
from config import DATA_DIR

_ROOT     = os.path.join(os.path.dirname(__file__), "..")
_HIST_DIR = os.path.join(_ROOT, "historial")

app = Flask(__name__)

_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Imai Dashboard</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', sans-serif; background: #0d1117; color: #c9d1d9; padding: 24px; }
h1  { color: #58a6ff; font-size: 1.4rem; margin-bottom: 20px; letter-spacing: 1px; }
.grid { display: grid; grid-template-columns: 320px 1fr; gap: 16px; }
.cam  { width: 100%; border-radius: 8px; background: #000; display: block; }
.col  { display: flex; flex-direction: column; gap: 16px; }
.card { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 18px; }
.card h2 { font-size: 0.85rem; text-transform: uppercase; letter-spacing: 1px; color: #8b949e; margin-bottom: 12px; }
.fact { padding: 5px 0; border-bottom: 1px solid #21262d; font-size: 0.88rem; line-height: 1.4; }
.fact:last-child { border-bottom: none; }
.entry { margin-bottom: 14px; }
.entry .ts { font-size: 0.72rem; color: #484f58; margin-bottom: 4px; }
.bubble { padding: 8px 12px; border-radius: 8px; font-size: 0.88rem; line-height: 1.5; margin-bottom: 4px; }
.bubble.user      { background: #1f2d3d; border-left: 3px solid #58a6ff; }
.bubble.assistant { background: #1a2b1a; border-left: 3px solid #3fb950; }
.badge { font-size: 0.7rem; background: #2d333b; color: #8b949e; padding: 1px 6px; border-radius: 4px; margin-left: 6px; }
.empty { color: #484f58; font-size: 0.85rem; }
.refresh { margin-top: 16px; font-size: 0.75rem; color: #484f58; }
.search { width: 100%; background: #0d1117; border: 1px solid #30363d; border-radius: 6px;
          color: #c9d1d9; padding: 7px 10px; font-size: 0.85rem; margin-bottom: 12px; outline: none; }
.search:focus { border-color: #58a6ff; }
</style>
</head>
<body>
<h1>★ Imai — delta Crucis</h1>
<div class="grid">
  <div class="col">
    <div class="card">
      <h2>Memoria</h2>
      <div id="memoria"><span class="empty">Cargando...</span></div>
    </div>
    <div class="card">
      <h2>Recordatorios</h2>
      <div id="recordatorios"><span class="empty">Cargando...</span></div>
    </div>
  </div>
  <div class="col" style="gap:16px">
    <div class="card">
      <h2>Cámara</h2>
      <img class="cam" src="/video_feed" alt="Sin señal">
    </div>
    <div class="card">
      <h2>Historial reciente</h2>
      <input id="buscar" class="search" type="text" placeholder="Buscar en historial...">
      <div id="historial"><span class="empty">Cargando...</span></div>
    </div>
  </div>
</div>
<p class="refresh">Actualización automática cada 20 s</p>
<script>
let _hist = [];

function renderHist(filtro) {
  filtro = filtro.toLowerCase().trim();
  const html = [];
  for (const e of _hist.slice().reverse()) {
    const msgs = (e.messages || []).filter(m => m.role !== 'system' && m.content);
    if (!msgs.length) continue;
    if (filtro && !msgs.some(m => m.content.toLowerCase().includes(filtro))) continue;
    html.push(`<div class="entry"><div class="ts">${e.timestamp || ''}${e.herramienta ? '<span class="badge">tool</span>' : ''}</div>`);
    for (const m of msgs) {
      const label = m.role === 'user' ? '👤 Tú' : '🤖 Imai';
      html.push(`<div class="bubble ${m.role}"><b>${label}</b> ${m.content.substring(0,400)}</div>`);
    }
    html.push('</div>');
  }
  document.getElementById('historial').innerHTML = html.join('') || '<span class="empty">Sin resultados</span>';
}

async function cargar() {
  const [mem, recs, hist] = await Promise.all([
    fetch('/api/memoria').then(r => r.json()),
    fetch('/api/recordatorios').then(r => r.json()),
    fetch('/api/historial').then(r => r.json()),
  ]);

  document.getElementById('memoria').innerHTML = mem.length
    ? mem.map(h => `<div class="fact">• ${h}</div>`).join('')
    : '<span class="empty">Sin datos guardados</span>';

  document.getElementById('recordatorios').innerHTML = recs.length
    ? recs.map(r => `<div class="fact">• ${r.mensaje} <span style="color:#484f58">${r.cuando}</span></div>`).join('')
    : '<span class="empty">Sin recordatorios</span>';

  _hist = hist;
  renderHist(document.getElementById('buscar').value);
}

document.getElementById('buscar').addEventListener('input', e => renderHist(e.target.value));
cargar();
setInterval(cargar, 20000);
</script>
</body>
</html>"""


@app.route("/")
def index():
    return render_template_string(_HTML)


@app.route("/api/memoria")
def api_memoria():
    try:
        with open(os.path.join(DATA_DIR, "memoria.json"), encoding="utf-8") as f:
            return jsonify(json.load(f))
    except Exception:
        return jsonify([])


@app.route("/api/recordatorios")
def api_recordatorios():
    try:
        with open(os.path.join(DATA_DIR, "recordatorios.json"), encoding="utf-8") as f:
            datos = json.load(f)
        return jsonify([{"mensaje": v["mensaje"], "cuando": v["cuando"]} for v in datos.values()])
    except Exception:
        return jsonify([])


@app.route("/video_feed")
def video_feed():
    import modules.camara as _cam
    def _generar():
        while True:
            frame = _cam.get_frame()
            if frame is not None:
                _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                       + buf.tobytes() + b"\r\n")
            time.sleep(0.05)
    return Response(_generar(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/api/historial")
def api_historial():
    archivos = sorted(glob.glob(os.path.join(_HIST_DIR, "*.jsonl")), reverse=True)
    entradas = []
    for archivo in archivos[:3]:
        try:
            with open(archivo, encoding="utf-8") as f:
                for linea in f:
                    try:
                        entradas.append(json.loads(linea))
                    except Exception:
                        pass
        except Exception:
            pass
    return jsonify(entradas[-60:])


def iniciar(puerto=5000):
    log = __import__("logging")
    log.getLogger("werkzeug").setLevel(log.ERROR)
    threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=puerto, debug=False, use_reloader=False),
        daemon=True,
        name="dashboard",
    ).start()
    print(f"[ Dashboard: http://localhost:{puerto} ]")
