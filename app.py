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
import time
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
        from PIL import Image, ImageDraw, ImageTk
        import pystray
        import Imai  # pre-carga Imai y todas sus dependencias (faster_whisper, anthropic, etc.)
        _loaded["ctk"]       = customtkinter
        _loaded["Image"]     = Image
        _loaded["ImageDraw"] = ImageDraw
        _loaded["ImageTk"]   = ImageTk
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
    ImageTk   = _loaded["ImageTk"]
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

            self._corriendo      = False
            self._tray           = None
            self._imai_thread    = None
            self._pulso          = False
            self._pulsar         = False
            self._dot_on         = _DIM
            self._dot_off        = _DIM
            self._turnos         = 0
            self._ultimo_msg_ts  = None   # para el separador de sesión

            self._construir_ui()
            self._set_window_icon()
            self._poll_log()
            self._animar_dot()
            self._animar_wave()

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

            fila = tk.Frame(card, bg=_PANEL)
            fila.pack(fill="x", pady=14, padx=18)

            self._dot_cv = tk.Canvas(fila, width=10, height=10,
                                     bg=_PANEL, highlightthickness=0)
            self._dot = self._dot_cv.create_oval(1, 1, 9, 9,
                                                  fill=_DIM, outline="")
            self._dot_cv.pack(side="left", padx=(0, 9))

            self._var_turnos = tk.StringVar(value="")
            tk.Label(fila, textvariable=self._var_turnos,
                     bg=_PANEL, fg=_DIM,
                     font=("Segoe UI", 8)).pack(side="right")

            self._var_estado = tk.StringVar(value="Detenido")
            self._lbl_estado = ctk.CTkLabel(fila,
                                            textvariable=self._var_estado,
                                            font=ctk.CTkFont("Segoe UI", 10),
                                            text_color=_DIM)
            self._lbl_estado.pack(side="left")

            # Waveform — 18 barras dentro de la card
            _N, _BW, _CH, _CW = 18, 3, 28, 268
            self._wave_cv = tk.Canvas(card, width=_CW, height=_CH,
                                      bg=_PANEL, highlightthickness=0)
            self._wave_cv.pack(pady=(0, 10))
            _gap = _CW / _N
            self._wave_bars = []
            for i in range(_N):
                cx = i * _gap + _gap / 2
                bar = self._wave_cv.create_rectangle(
                    cx - _BW / 2, _CH - 2, cx + _BW / 2, _CH,
                    fill=_BORDE, outline="")
                self._wave_bars.append(bar)

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

            # Cabecera del chat
            hdr = tk.Frame(self, bg=_BG)
            hdr.pack(fill="x", padx=26, pady=(0, 5))
            tk.Label(hdr, text="CHAT", bg=_BG, fg=_DIM,
                     font=("Segoe UI", 7, "bold")).pack(side="left")
            tk.Button(hdr, text="limpiar", bg=_BG, fg=_DIM,
                      relief="flat", bd=0, font=("Segoe UI", 7),
                      cursor="hand2", activebackground=_BG,
                      activeforeground=_GRIS,
                      command=self._limpiar_chat).pack(side="right")

            # Área de burbujas
            chat_frame = ctk.CTkFrame(self, fg_color=_PANEL,
                                      corner_radius=10,
                                      border_width=1, border_color=_BORDE)
            chat_frame.pack(fill="both", expand=True, padx=24, pady=(0, 24))

            self._chat = ctk.CTkScrollableFrame(chat_frame, fg_color=_PANEL,
                                                scrollbar_button_color=_BORDE,
                                                scrollbar_button_hover_color=_GRIS)
            self._chat.pack(fill="both", expand=True, padx=2, pady=2)

        # ── Chat burbujas ─────────────────────────────────────────────────────

        def _agregar_separador(self, dt: datetime):
            hora = dt.strftime("%H:%M")
            fila = tk.Frame(self._chat, bg=_PANEL)
            fila.pack(fill="x", padx=10, pady=10)
            tk.Frame(fila, bg=_BORDE, height=1).pack(
                side="left", fill="x", expand=True, pady=5)
            tk.Label(fila, text=f"  {hora}  ", bg=_PANEL, fg=_DIM,
                     font=("Segoe UI", 7)).pack(side="left")
            tk.Frame(fila, bg=_BORDE, height=1).pack(
                side="left", fill="x", expand=True, pady=5)

        def _agregar_burbuja(self, texto: str, rol: str):
            ahora = datetime.now()

            # Separador si pasaron más de 5 minutos desde el último mensaje
            if self._ultimo_msg_ts is not None:
                delta = (ahora - self._ultimo_msg_ts).total_seconds() / 60
                if delta >= 5:
                    self._agregar_separador(ahora)
            self._ultimo_msg_ts = ahora

            es_user = (rol == "user")
            ts      = ahora.strftime("%H:%M")
            color_burbuja = "#1f2d3d" if es_user else "#1a2b1a"
            color_sender  = _AZUL if es_user else _VERDE
            nombre        = "Tú" if es_user else "Imai"
            anchor        = "e" if es_user else "w"

            # Contenedor del mensaje
            cont = tk.Frame(self._chat, bg=_PANEL)
            cont.pack(fill="x", pady=(4, 0), padx=6)

            # Nombre del remitente
            tk.Label(cont, text=nombre, bg=_PANEL, fg=color_sender,
                     font=("Segoe UI", 7, "bold")).pack(anchor=anchor, padx=4)

            # Burbuja
            burbuja = ctk.CTkFrame(cont, fg_color=color_burbuja, corner_radius=12)
            burbuja.pack(anchor=anchor, padx=2)

            ctk.CTkLabel(burbuja,
                         text=texto,
                         font=ctk.CTkFont("Segoe UI", 10),
                         text_color="#e6edf3",
                         wraplength=215,
                         justify="right" if es_user else "left",
                         anchor="e" if es_user else "w").pack(
                             padx=12, pady=(8, 2), anchor=anchor)

            tk.Label(burbuja, text=ts, bg=color_burbuja, fg=_DIM,
                     font=("Segoe UI", 7)).pack(
                         anchor="e", padx=10, pady=(0, 6))

            # Scroll al fondo
            self.after(60, self._scroll_fondo)

            # Toast si está en el tray
            if not es_user and self._tray:
                try:
                    self._tray.notify(texto[:100], "★ Imai")
                except Exception:
                    pass

        def _agregar_sistema(self, texto: str):
            tk.Label(self._chat, text=f"— {texto} —",
                     bg=_PANEL, fg=_DIM,
                     font=("Segoe UI", 7)).pack(pady=6)
            self.after(60, self._scroll_fondo)

        def _limpiar_chat(self):
            for w in self._chat.winfo_children():
                w.destroy()

        def _scroll_fondo(self):
            try:
                self._chat._parent_canvas.yview_moveto(1.0)
            except Exception:
                pass

        def _poll_log(self):
            try:
                while True:
                    msg = _log_queue.get_nowait()
                    try:
                        if msg.startswith("Tu:"):
                            txt = msg[3:].strip()
                            if txt:
                                self._agregar_burbuja(txt, "user")
                            self._turnos += 1
                            self._var_turnos.set(f"{self._turnos} {'turno' if self._turnos == 1 else 'turnos'}")
                            self._set_estado("Procesando...", _AMARILLO, pulsar=False)
                        elif msg.startswith("Imai:"):
                            txt = msg[5:].strip()
                            if txt:
                                self._agregar_burbuja(txt, "imai")
                            self._set_estado("Respondiendo...", _AZUL, pulsar=False)
                        elif "Escuchando..." in msg:
                            self._set_estado("Escuchando...", _VERDE, pulsar=True)
                        elif "[ Tool:" in msg:
                            self._set_estado("Ejecutando...", _AMARILLO, pulsar=False)
                    except Exception:
                        pass
            except queue.Empty:
                pass
            self.after(100, self._poll_log)

        # ── Animación e ícono ─────────────────────────────────────────────────

        def _set_window_icon(self):
            try:
                img  = self._icono().resize((32, 32), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self.wm_iconphoto(True, photo)
                self._win_icon = photo   # evitar GC
            except Exception:
                pass

        def _set_estado(self, texto: str, color: str, pulsar: bool = False):
            self._var_estado.set(texto)
            self._lbl_estado.configure(text_color=color)
            self._pulsar  = pulsar
            self._dot_on  = color
            self._dot_off = self._oscurecer(color)
            if not pulsar:
                self._dot_cv.itemconfig(self._dot, fill=color)

        @staticmethod
        def _oscurecer(hex_color: str) -> str:
            r = int(hex_color[1:3], 16) // 3
            g = int(hex_color[3:5], 16) // 3
            b = int(hex_color[5:7], 16) // 3
            return f"#{r:02x}{g:02x}{b:02x}"

        def _animar_dot(self):
            if self._pulsar:
                self._pulso = not self._pulso
                self._dot_cv.itemconfig(
                    self._dot,
                    fill=self._dot_on if self._pulso else self._dot_off)
            self.after(500, self._animar_dot)

        def _animar_wave(self):
            _CH   = 28
            _BMIN = 2
            _BMAX = 26
            try:
                import modules.stt as _stt
                nivel = getattr(_stt, "nivel_audio", 0.0) if self._pulsar else 0.0
            except Exception:
                nivel = 0.0

            now = time.time()
            for i, bar in enumerate(self._wave_bars):
                if nivel > 0.02:
                    phase = now * 9 + i * 0.65
                    wave  = (math.sin(phase) + 1) / 2
                    h = int(_BMIN + wave * nivel * (_BMAX - _BMIN))
                    color = _VERDE
                else:
                    h = _BMIN
                    color = _BORDE
                coords = self._wave_cv.coords(bar)
                if coords:
                    x1, _, x2, _ = coords
                    self._wave_cv.coords(bar, x1, _CH - h, x2, _CH)
                    self._wave_cv.itemconfig(bar, fill=color)

            self.after(50, self._animar_wave)

        # ── Control ───────────────────────────────────────────────────────────

        def _toggle(self):
            if not self._corriendo:
                self._iniciar()
            else:
                self._detener()

        def _iniciar(self):
            # Fix: esperar sin bloquear la UI a que el hilo anterior muera
            if self._imai_thread and self._imai_thread.is_alive():
                self.after(150, self._iniciar)
                return
            self._corriendo = True
            self._btn.configure(text="⏹   DETENER",
                                fg_color=_ROJO, hover_color="#f85149",
                                state="normal")
            self._set_estado("Iniciando...", _GRIS, pulsar=False)
            # Fix: limpiar chat al iniciar nueva sesión
            self._limpiar_chat()
            self._ultimo_msg_ts = None
            sys.stdout = _StdoutCapture(_log_queue)
            self._imai_thread = threading.Thread(
                target=self._run_imai, daemon=True, name="imai-main")
            self._imai_thread.start()
            self._agregar_sistema("Imai iniciado")
            self._actualizar_tray()

        def _detener(self):
            try:
                import Imai
                Imai._STOP.set()
            except Exception:
                pass
            try:
                import modules.stt as _stt
                _stt.parar()
            except Exception:
                pass
            try:
                import modules.tts as _tts
                _tts.parar()
            except Exception:
                pass
            try:
                import modules.proactivo as _proact
                _proact.pausar()
            except Exception:
                pass
            self._corriendo = False
            self._pulsar    = False
            self._turnos    = 0
            self._var_turnos.set("")
            sys.stdout = sys.__stdout__
            # Fix: deshabilitar botón hasta que el hilo muera realmente
            self._btn.configure(text="⏳  Deteniendo...",
                                fg_color=_DIM, hover_color=_DIM,
                                state="disabled")
            self._set_estado("Detenido", _DIM, pulsar=False)
            self._agregar_sistema("Imai detenido")
            self._actualizar_tray()
            self._aguardar_hilo()

        def _aguardar_hilo(self):
            """Polling no-bloqueante: re-habilita el botón cuando el hilo muere."""
            if self._imai_thread and self._imai_thread.is_alive():
                self.after(150, self._aguardar_hilo)
            else:
                self._btn.configure(text="▶   INICIAR IMAI",
                                    fg_color="#238636", hover_color="#2ea043",
                                    state="normal")

        def _run_imai(self):
            try:
                import Imai
                import modules.stt as _stt
                Imai._STOP.clear()
                _stt.limpiar_stop()
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
            else:
                # hilo terminó solo (ej: "salir"), asegurar botón habilitado
                self._btn.configure(text="▶   INICIAR IMAI",
                                    fg_color="#238636", hover_color="#2ea043",
                                    state="normal")

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
    ImaiApp().mainloop()
