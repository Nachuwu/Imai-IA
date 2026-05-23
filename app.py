"""
app.py — Lanzador gráfico de Imai
Ventana con botón Iniciar/Detener + log de actividad.
Cerrar X → minimiza a la bandeja del sistema (Imai sigue corriendo).
Doble clic en el icono del tray → restaura la ventana.
"""
import math
import os
import queue
import sys
import threading
import webbrowser
import tkinter as tk

from PIL import Image, ImageDraw
import pystray

_log_queue: queue.Queue = queue.Queue()


class _StdoutCapture:
    """Redirige stdout al queue del log y mantiene la salida original."""
    def __init__(self, q: queue.Queue):
        self._q = q
        self._orig = sys.__stdout__

    def write(self, texto: str):
        if texto and texto.strip():
            self._q.put(texto.strip())
        if self._orig:
            self._orig.write(texto)
        return len(texto)

    def flush(self):
        if self._orig:
            self._orig.flush()

    def isatty(self):
        return False


class ImaiApp:
    _BG      = "#0d1117"
    _PANEL   = "#161b22"
    _BORDE   = "#30363d"
    _AZUL    = "#58a6ff"
    _VERDE   = "#3fb950"
    _ROJO    = "#da3633"
    _AMARILLO= "#d29922"
    _GRIS    = "#8b949e"
    _DIM     = "#484f58"

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Imai")
        self.root.geometry("400x520")
        self.root.resizable(False, False)
        self.root.configure(bg=self._BG)
        self.root.protocol("WM_DELETE_WINDOW", self._ir_a_tray)

        self._corriendo   = False
        self._imai_thread = None
        self._tray        = None

        self._construir_ui()
        self._poll_log()

    # ── UI ───────────────────────────────────────────────────────────────────

    def _construir_ui(self):
        # Título
        tk.Label(self.root, text="★  Imai — delta Crucis",
                 bg=self._BG, fg=self._AZUL,
                 font=("Segoe UI", 15, "bold")).pack(pady=(24, 6))

        # Estado
        self._var_estado = tk.StringVar(value="● Detenido")
        self._lbl_estado = tk.Label(self.root,
                                    textvariable=self._var_estado,
                                    bg=self._BG, fg=self._DIM,
                                    font=("Segoe UI", 10))
        self._lbl_estado.pack(pady=(0, 20))

        # Botón principal
        self._btn = tk.Button(self.root,
                              text="▶   INICIAR IMAI",
                              command=self._toggle,
                              bg="#238636", fg="white",
                              font=("Segoe UI", 12, "bold"),
                              relief="flat", bd=0,
                              padx=32, pady=14,
                              cursor="hand2",
                              activebackground="#2ea043",
                              activeforeground="white")
        self._btn.pack(pady=(0, 12))

        # Dashboard
        tk.Button(self.root,
                  text="🌐  Abrir Dashboard",
                  command=lambda: webbrowser.open("https://localhost:5000"),
                  bg=self._PANEL, fg=self._AZUL,
                  font=("Segoe UI", 9),
                  relief="flat", bd=0,
                  padx=14, pady=7,
                  cursor="hand2",
                  activebackground="#21262d",
                  activeforeground=self._AZUL).pack(pady=(0, 18))

        # Separador
        tk.Frame(self.root, bg=self._BORDE, height=1).pack(fill="x", padx=20, pady=(0, 8))
        tk.Label(self.root, text="ACTIVIDAD",
                 bg=self._BG, fg=self._DIM,
                 font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=22)

        # Log
        marco = tk.Frame(self.root, bg=self._PANEL,
                         highlightthickness=1,
                         highlightbackground=self._BORDE)
        marco.pack(fill="both", expand=True, padx=20, pady=(4, 20))

        scroll = tk.Scrollbar(marco, bg=self._PANEL)
        scroll.pack(side="right", fill="y")

        self._log = tk.Text(marco,
                            bg=self._PANEL, fg="#c9d1d9",
                            font=("Consolas", 9),
                            relief="flat", bd=8,
                            state="disabled", wrap="word",
                            yscrollcommand=scroll.set)
        self._log.pack(fill="both", expand=True)
        scroll.config(command=self._log.yview)

        self._log.tag_config("user",   foreground=self._AZUL)
        self._log.tag_config("imai",   foreground=self._VERDE)
        self._log.tag_config("tool",   foreground=self._AMARILLO)
        self._log.tag_config("system", foreground=self._GRIS)
        self._log.tag_config("error",  foreground=self._ROJO)
        self._log.tag_config("dim",    foreground=self._DIM)

    # ── log ──────────────────────────────────────────────────────────────────

    def _escribir_log(self, texto: str, tag: str = "dim"):
        self._log.config(state="normal")
        self._log.insert("end", texto + "\n", tag)
        self._log.see("end")
        self._log.config(state="disabled")

    def _poll_log(self):
        try:
            while True:
                msg = _log_queue.get_nowait()
                if msg.startswith("Tu:"):
                    self._escribir_log(msg, "user")
                elif msg.startswith("Imai:"):
                    self._escribir_log(msg, "imai")
                elif msg.startswith("[ Tool:"):
                    self._escribir_log(msg, "tool")
                elif msg.startswith("[") or msg.startswith(" *"):
                    self._escribir_log(msg, "system")
                elif "rror" in msg:
                    self._escribir_log(msg, "error")
                else:
                    self._escribir_log(msg, "dim")
        except queue.Empty:
            pass
        self.root.after(100, self._poll_log)

    # ── control ──────────────────────────────────────────────────────────────

    def _toggle(self):
        if not self._corriendo:
            self._iniciar()
        else:
            self._detener()

    def _iniciar(self):
        self._corriendo = True
        self._btn.config(text="⏹   DETENER",
                         bg=self._ROJO, activebackground="#f85149")
        self._var_estado.set("● Escuchando...")
        self._lbl_estado.config(fg=self._VERDE)

        sys.stdout = _StdoutCapture(_log_queue)

        try:
            import Imai
            Imai._STOP.clear()
        except Exception:
            pass

        self._imai_thread = threading.Thread(
            target=self._run_imai, daemon=True, name="imai-main")
        self._imai_thread.start()
        self._escribir_log("Imai iniciado.", "imai")
        self._actualizar_tray()

    def _detener(self):
        try:
            import Imai
            Imai._STOP.set()
        except Exception:
            pass
        self._corriendo = False
        sys.stdout = sys.__stdout__
        self._btn.config(text="▶   INICIAR IMAI",
                         bg="#238636", activebackground="#2ea043")
        self._var_estado.set("● Detenido")
        self._lbl_estado.config(fg=self._DIM)
        self._escribir_log("Imai detenido.", "dim")
        self._actualizar_tray()

    def _run_imai(self):
        try:
            import Imai
            Imai.main()
        except SystemExit:
            pass
        except Exception as e:
            _log_queue.put(f"Error: {e}")
        finally:
            self.root.after(0, self._on_imai_exit)

    def _on_imai_exit(self):
        if self._corriendo:
            self._detener()

    # ── tray ─────────────────────────────────────────────────────────────────

    def _ir_a_tray(self):
        self.root.withdraw()
        if not self._tray:
            self._crear_tray()

    def _crear_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem("★ Imai — delta Crucis", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Abrir", lambda: self.root.after(0, self._restaurar), default=True),
            pystray.MenuItem("Dashboard",
                             lambda: webbrowser.open("https://localhost:5000")),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Salir", self._salir),
        )
        self._tray = pystray.Icon("Imai", self._icono(), "Imai", menu)
        threading.Thread(target=self._tray.run, daemon=True, name="tray").start()

    def _restaurar(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        if self._tray:
            self._tray.stop()
            self._tray = None

    def _actualizar_tray(self):
        if self._tray:
            self._tray.icon = self._icono()

    def _salir(self):
        try:
            import Imai
            Imai._STOP.set()
        except Exception:
            pass
        if self._tray:
            self._tray.stop()
        os._exit(0)

    def _icono(self) -> Image.Image:
        size = 64
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        fondo = (35, 134, 54, 240) if self._corriendo else (22, 27, 34, 240)
        d.ellipse([2, 2, size - 2, size - 2],
                  fill=fondo, outline=(48, 54, 61, 255), width=2)

        cx, cy = size // 2, size // 2
        pts = []
        for i in range(10):
            angle = math.pi / 2 - i * math.pi / 5
            r = 20 if i % 2 == 0 else 8
            pts.append((cx + r * math.cos(angle), cy - r * math.sin(angle)))
        d.polygon(pts, fill=(88, 166, 255, 255))

        return img

    # ── run ──────────────────────────────────────────────────────────────────

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    ImaiApp().run()
