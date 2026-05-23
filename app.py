"""
app.py — Lanzador gráfico de Imai
Splash inmediato → imports pesados en background → ventana principal.
"""
import math
import os
import queue
import socket
import sys
import threading
import webbrowser
import tkinter as tk
import tkinter.messagebox as _mb
from datetime import datetime

# ── Paleta ────────────────────────────────────────────────────────────────────
_BG       = "#0d1117"
_PANEL    = "#161b22"
_PANEL2   = "#1c2128"
_BORDE    = "#30363d"
_AZUL     = "#58a6ff"
_VERDE    = "#3fb950"
_ROJO     = "#da3633"
_AMARILLO = "#d29922"
_GRIS     = "#8b949e"
_DIM      = "#484f58"

_TAILSCALE_IP = "100.90.28.44"
_log_queue: queue.Queue = queue.Queue()


# ── Stdout capture ────────────────────────────────────────────────────────────
class _StdoutCapture:
    def __init__(self, q: queue.Queue):
        self._q, self._orig = q, sys.__stdout__

    def write(self, t: str):
        if t and t.strip():
            self._q.put(t.strip())
        if self._orig:
            self._orig.write(t)
        return len(t)

    def flush(self):
        if self._orig:
            self._orig.flush()

    def isatty(self):
        return False


# ── Splash (solo tkinter, aparece en <200 ms) ─────────────────────────────────
def _splash() -> tk.Tk:
    s = tk.Tk()
    s.overrideredirect(True)
    s.configure(bg=_BG)
    w, h = 260, 110
    sw, sh = s.winfo_screenwidth(), s.winfo_screenheight()
    s.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")
    tk.Label(s, text="★  Imai", bg=_BG, fg=_AZUL,
             font=("Segoe UI", 22, "bold")).pack(expand=True, pady=(20, 4))
    tk.Label(s, text="Iniciando...", bg=_BG, fg=_DIM,
             font=("Segoe UI", 9)).pack(pady=(0, 20))
    s.update()
    return s


# ── Punto de entrada ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Instancia única — el socket queda abierto hasta que el proceso muere
    _lock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        _lock.bind(("127.0.0.1", 47291))
    except OSError:
        _r = tk.Tk()
        _r.withdraw()
        _mb.showinfo("Imai",
                     "Imai ya está en ejecución.\n"
                     "Búscalo en la bandeja del sistema (esquina inferior derecha).")
        _r.destroy()
        sys.exit(0)

    splash = _splash()           # visible de inmediato

    # Imports pesados en hilo de fondo — splash sigue respondiendo
    _loaded: dict = {}
    _imports_done = threading.Event()

    def _cargar():
        import customtkinter
        from PIL import Image, ImageDraw
        import pystray
        _loaded["ctk"]       = customtkinter
        _loaded["Image"]     = Image
        _loaded["ImageDraw"] = ImageDraw
        _loaded["pystray"]   = pystray
        _imports_done.set()

    threading.Thread(target=_cargar, daemon=True).start()

    # Esperar con el event loop activo (splash responde durante la espera)
    def _check_listos():
        if _imports_done.is_set():
            splash.quit()
        else:
            splash.after(40, _check_listos)

    splash.after(40, _check_listos)
    splash.mainloop()
    splash.destroy()

    ctk       = _loaded["ctk"]
    Image     = _loaded["Image"]
    ImageDraw = _loaded["ImageDraw"]
    pystray   = _loaded["pystray"]

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    # ── App principal ─────────────────────────────────────────────────────────
    class ImaiApp(ctk.CTk):
        def __init__(self):
            super().__init__()
            self.title("Imai")
            self.geometry("380x620")
            self.resizable(False, False)
            self.configure(fg_color=_BG)
            self.protocol("WM_DELETE_WINDOW", self._ir_a_tray)

            self._corriendo   = False
            self._tray        = None
            self._imai_thread = None
            self._pulso       = False

            self._construir_ui()
            self._poll_log()
            self._animar_dot()

        # ── UI ────────────────────────────────────────────────────────────────

        def _construir_ui(self):
            ctk.CTkLabel(self,
                         text="★  Imai",
                         font=ctk.CTkFont("Segoe UI", 24, "bold"),
                         text_color=_AZUL).pack(pady=(28, 2))

            ctk.CTkLabel(self,
                         text="delta Crucis",
                         font=ctk.CTkFont("Segoe UI", 11),
                         text_color=_DIM).pack(pady=(0, 22))

            # Card de estado
            card = ctk.CTkFrame(self, fg_color=_PANEL,
                                corner_radius=12,
                                border_width=1, border_color=_BORDE)
            card.pack(fill="x", padx=24, pady=(0, 14))

            fila = ctk.CTkFrame(card, fg_color="transparent")
            fila.pack(pady=14, padx=18)

            self._dot_cv = tk.Canvas(fila, width=10, height=10,
                                     bg=_PANEL, highlightthickness=0)
            self._dot = self._dot_cv.create_oval(1, 1, 9, 9,
                                                  fill=_DIM, outline="")
            self._dot_cv.pack(side="left", padx=(0, 9))

            self._var_estado = tk.StringVar(value="Detenido")
            self._lbl_estado = ctk.CTkLabel(fila,
                                            textvariable=self._var_estado,
                                            font=ctk.CTkFont("Segoe UI", 10),
                                            text_color=_DIM)
            self._lbl_estado.pack(side="left")

            # Botón principal
            self._btn = ctk.CTkButton(self,
                                      text="▶   INICIAR IMAI",
                                      command=self._toggle,
                                      font=ctk.CTkFont("Segoe UI", 13, "bold"),
                                      fg_color="#238636",
                                      hover_color="#2ea043",
                                      height=50,
                                      corner_radius=10)
            self._btn.pack(fill="x", padx=24, pady=(0, 10))

            # Botones secundarios
            fila_sec = tk.Frame(self, bg=_BG)
            fila_sec.pack(fill="x", padx=24, pady=(0, 22))

            ctk.CTkButton(fila_sec,
                          text="🌐  Dashboard",
                          command=lambda: webbrowser.open("https://localhost:5000"),
                          font=ctk.CTkFont("Segoe UI", 10),
                          fg_color=_PANEL, hover_color=_PANEL2,
                          text_color=_AZUL,
                          border_width=1, border_color=_BORDE,
                          height=34, corner_radius=8).pack(
                              side="left", expand=True, fill="x", padx=(0, 5))

            ctk.CTkButton(fila_sec,
                          text="📱  Móvil",
                          command=lambda: webbrowser.open(
                              f"https://{_TAILSCALE_IP}:5000/movil"),
                          font=ctk.CTkFont("Segoe UI", 10),
                          fg_color=_PANEL, hover_color=_PANEL2,
                          text_color=_GRIS,
                          border_width=1, border_color=_BORDE,
                          height=34, corner_radius=8).pack(
                              side="left", expand=True, fill="x", padx=(5, 0))

            # Separador
            ctk.CTkFrame(self, height=1, fg_color=_BORDE,
                         corner_radius=0).pack(fill="x", padx=24, pady=(0, 10))

            # Cabecera del log
            hdr = tk.Frame(self, bg=_BG)
            hdr.pack(fill="x", padx=26, pady=(0, 5))
            tk.Label(hdr, text="CHAT", bg=_BG, fg=_DIM,
                     font=("Segoe UI", 7, "bold")).pack(side="left")
            tk.Button(hdr, text="limpiar", bg=_BG, fg=_DIM,
                      relief="flat", bd=0, font=("Segoe UI", 7),
                      cursor="hand2", activebackground=_BG,
                      activeforeground=_GRIS,
                      command=self._limpiar_log).pack(side="right")

            # Área de log
            log_frame = ctk.CTkFrame(self, fg_color=_PANEL,
                                     corner_radius=10,
                                     border_width=1, border_color=_BORDE)
            log_frame.pack(fill="both", expand=True, padx=24, pady=(0, 24))

            scroll = tk.Scrollbar(log_frame, bg=_PANEL,
                                  troughcolor=_PANEL, relief="flat", bd=0)
            scroll.pack(side="right", fill="y")

            self._log = tk.Text(log_frame, bg=_PANEL, fg="#c9d1d9",
                                font=("Consolas", 9), relief="flat", bd=10,
                                state="disabled", wrap="word", cursor="arrow",
                                selectbackground=_BORDE,
                                inactiveselectbackground=_BORDE,
                                yscrollcommand=scroll.set)
            self._log.pack(fill="both", expand=True)
            scroll.config(command=self._log.yview)

            self._log.tag_config("ts",     foreground=_DIM)
            self._log.tag_config("user",   foreground=_AZUL)
            self._log.tag_config("imai",   foreground=_VERDE)
            self._log.tag_config("tool",   foreground=_AMARILLO)
            self._log.tag_config("system", foreground=_GRIS)
            self._log.tag_config("error",  foreground=_ROJO)
            self._log.tag_config("dim",    foreground=_DIM)

        # ── Log ───────────────────────────────────────────────────────────────

        def _escribir_log(self, texto: str, tag: str = "dim"):
            ts = datetime.now().strftime("%H:%M")
            self._log.config(state="normal")
            self._log.insert("end", f"{ts}  ", "ts")
            self._log.insert("end", texto + "\n", tag)
            self._log.see("end")
            self._log.config(state="disabled")

        def _limpiar_log(self):
            self._log.config(state="normal")
            self._log.delete("1.0", "end")
            self._log.config(state="disabled")

        def _poll_log(self):
            try:
                while True:
                    msg = _log_queue.get_nowait()
                    if msg.startswith("Tu:"):
                        self._escribir_log(msg, "user")
                    elif msg.startswith("Imai:"):
                        self._escribir_log(msg, "imai")
            except queue.Empty:
                pass
            self.after(100, self._poll_log)

        # ── Animación ─────────────────────────────────────────────────────────

        def _animar_dot(self):
            if self._corriendo:
                self._pulso = not self._pulso
                color = _VERDE if self._pulso else "#1a5c2a"
                self._dot_cv.itemconfig(self._dot, fill=color)
            self.after(600, self._animar_dot)

        # ── Control ───────────────────────────────────────────────────────────

        def _toggle(self):
            if not self._corriendo:
                self._iniciar()
            else:
                self._detener()

        def _iniciar(self):
            self._corriendo = True
            self._btn.configure(text="⏹   DETENER",
                                fg_color=_ROJO, hover_color="#f85149")
            self._var_estado.set("Escuchando...")
            self._lbl_estado.configure(text_color=_VERDE)
            self._dot_cv.itemconfig(self._dot, fill=_VERDE)

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
            self._btn.configure(text="▶   INICIAR IMAI",
                                fg_color="#238636", hover_color="#2ea043")
            self._var_estado.set("Detenido")
            self._lbl_estado.configure(text_color=_DIM)
            self._dot_cv.itemconfig(self._dot, fill=_DIM)
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
                self.after(0, self._on_imai_exit)

        def _on_imai_exit(self):
            if self._corriendo:
                self._detener()

        # ── Tray ──────────────────────────────────────────────────────────────

        def _ir_a_tray(self):
            self.withdraw()
            if not self._tray:
                self._crear_tray()

        def _crear_tray(self):
            menu = pystray.Menu(
                pystray.MenuItem("★ Imai — delta Crucis", None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(
                    "Abrir", lambda: self.after(0, self._restaurar), default=True),
                pystray.MenuItem(
                    "Dashboard",
                    lambda: webbrowser.open("https://localhost:5000")),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Salir", self._salir),
            )
            self._tray = pystray.Icon("Imai", self._icono(), "Imai", menu)
            threading.Thread(
                target=self._tray.run, daemon=True, name="tray").start()

        def _restaurar(self):
            self.deiconify()
            self.lift()
            self.focus_force()
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

    # ── Lanzar ────────────────────────────────────────────────────────────────
    splash.destroy()
    ImaiApp().mainloop()
