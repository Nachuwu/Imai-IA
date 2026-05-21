"""
Dispatcher que mapea nombre de tool → implementación real.
Las definiciones de herramientas están en modules/claude_llm.py (formato Anthropic).
"""


def ejecutar(nombre, args, hablar_cb=None):
    """Despacha una tool call a la implementación real. Retorna string con el resultado."""
    import webbrowser
    import modules.tools as _t
    import modules.apps as _apps
    import modules.urls as _urls
    import modules.memoria as _mem
    from modules.stt import pausar as _pausar

    # --- Volumen ---
    if nombre == "volumen":
        accion = args.get("accion")
        if accion == "establecer":  return _t.set_volumen(args.get("pct", 50))
        if accion == "subir":       return _t.subir_volumen()
        if accion == "bajar":       return _t.bajar_volumen()
        if accion == "silenciar":   return _t.silenciar()
        if accion == "activar":     return _t.activar_sonido()
        return _t.get_volumen()

    # --- Brillo ---
    if nombre == "brillo":
        accion = args.get("accion")
        if accion == "establecer":  return _t.set_brillo(args.get("pct", 50))
        if accion == "subir":       return _t.subir_brillo()
        if accion == "bajar":       return _t.bajar_brillo()
        return _t.get_brillo()

    # --- Timer ---
    if nombre == "timer":
        accion = args.get("accion")
        if accion == "crear":
            segundos = args.get("segundos", 60)
            def _cb(msg):
                _t.notificar("Imai — Timer", msg)
                if hablar_cb:
                    hablar_cb(msg)
            return _t.crear_timer(segundos, _cb)
        return _t.cancelar_timer()

    # --- Spotify ---
    if nombre == "spotify":
        accion = args.get("accion")
        if accion == "siguiente":   _t.spotify_siguiente();  return ""
        if accion == "anterior":    _t.spotify_anterior();   return ""
        if accion == "parar":       _t.spotify_parar();      return ""
        if accion == "que_suena":   return _t.get_cancion_spotify()
        _t.spotify_play_pause();    return ""

    # --- Apps ---
    if nombre == "abrir_app":
        nombre_app = args.get("nombre", "")
        key = _apps.abrir(nombre_app)
        return f"Abriendo {key}." if key else f"No encontré {nombre_app}."

    if nombre == "cerrar_app":
        nombre_app = args.get("nombre", "")
        key = _apps.cerrar(nombre_app)
        return f"Cerrando {key}." if key else f"No encontré {nombre_app} ejecutándose."

    # --- Archivos ---
    if nombre == "buscar_archivo":
        return _t.buscar_archivos(args.get("nombre", "")) or "No encontré el archivo."

    # --- Info ---
    if nombre == "hora":            return _t.get_hora()
    if nombre == "fecha":           return _t.get_fecha()
    if nombre == "clima":           return _t.get_clima(args.get("ciudad", "Santiago"))
    if nombre == "portapapeles":    return _t.get_portapapeles()
    if nombre == "captura_pantalla": return _t.captura_pantalla()

    # --- Calculadora ---
    if nombre == "calcular":
        resultado = _t.calcular(args.get("expresion", ""))
        return f"{resultado}." if resultado else "No pude calcular eso."

    # --- Web ---
    if nombre == "abrir_sitio":
        return _urls.manejar(args.get("sitio", ""))

    if nombre == "buscar_youtube":
        query = args.get("query", "")
        directo = _urls._abrir_primer_resultado_yt(query)
        return f"Reproduciendo {query} en YouTube." if directo else f"Buscando {query} en YouTube."

    if nombre == "buscar_google":
        query = args.get("query", "")
        webbrowser.open(f"https://www.google.com/search?q={query.replace(' ', '+')}")
        return f"Buscando {query} en Google."

    # --- Memoria ---
    if nombre == "guardar_memoria":
        hecho = args.get("hecho", "")
        if hecho:
            _mem.agregar(hecho)
            return f"Anotado: {hecho}."
        return "¿Qué quieres que recuerde?"

    if nombre == "guardar_perfil":
        campo = args.get("campo", "")
        valor = args.get("valor", "")
        if campo and valor:
            _mem.agregar_perfil(campo, valor)
            return f"Perfil actualizado: {campo} = {valor}."
        return "Necesito el campo y el valor."

    # --- No molestar ---
    if nombre == "no_molestar":
        segundos = args.get("segundos", 300)
        _pausar(segundos)
        def _reanudar(msg):
            if hablar_cb:
                hablar_cb("Ya puedes hablarme.")
        _t.crear_timer(segundos, _reanudar)
        return f"De acuerdo, silencio por {_t._fmt_tiempo(segundos)}."

    # --- Ventanas ---
    if nombre == "ventana":
        return _t.controlar_ventana(args.get("accion", "listar"), args.get("titulo"))

    # --- Recordatorios ---
    if nombre == "recordatorio":
        import modules.recordatorios as _rec
        return _rec.crear(args.get("mensaje", ""), args.get("cuando", ""))

    if nombre == "listar_recordatorios":
        import modules.recordatorios as _rec
        return _rec.listar()

    if nombre == "cancelar_recordatorio":
        import modules.recordatorios as _rec
        return _rec.cancelar_ultimo()

    if nombre == "alarma_recurrente":
        import modules.recordatorios as _rec
        return _rec.crear_recurrente(
            args.get("mensaje", ""),
            args.get("hora", "08:00"),
            args.get("frecuencia", "diario"),
        )

    if nombre == "historial_spotify":
        return _t.historial_spotify(args.get("n", 10))

    # --- Control de mouse/teclado ---
    if nombre == "control_input":
        accion = args.get("accion")
        if accion == "escribir":    return _t.escribir_teclado(args.get("texto", ""))
        if accion == "tecla":       return _t.presionar_tecla(args.get("combo", "enter"))
        if accion == "scroll":      return _t.scroll_pantalla(args.get("direccion", "abajo"), args.get("cantidad", 3))
        if accion == "click":       return _t.click_en(args.get("x", 0), args.get("y", 0))
        if accion == "click_texto": return _t.click_en_texto(args.get("texto", ""))
        return "Acción no reconocida."

    # --- Gmail ---
    if nombre == "leer_correos":
        import modules.gmail as _gmail
        return _gmail.leer_correos(args.get("n", 5))

    if nombre == "enviar_correo":
        import modules.gmail as _gmail
        return _gmail.enviar_correo(
            args.get("destinatario", ""),
            args.get("asunto", ""),
            args.get("cuerpo", ""),
        )

    # --- Memoria vectorial ---
    if nombre == "buscar_memoria":
        import modules.memoria as _mem2
        return _mem2.buscar_semantico(args.get("query", ""))

    if nombre == "control_pc":
        accion = args.get("accion")
        if accion == "apagar":        return _t.apagar_pc()
        if accion == "reiniciar":     return _t.reiniciar_pc()
        if accion == "bloquear":      return _t.bloquear_pantalla()
        if accion == "suspender":     return _t.suspender_pc()
        if accion == "cancelar_apagado": return _t.cancelar_apagado()

    if nombre == "actualizar_memoria":
        import modules.memoria as _mem2
        hecho   = args.get("hecho_nuevo", "")
        patron  = args.get("patron")
        if hecho:
            reemplazado = _mem2.actualizar(hecho, patron)
            return f"Actualizado: {hecho}." if reemplazado else f"Anotado: {hecho}."
        return "¿Qué quieres actualizar?"

    # --- Búsqueda web ---
    if nombre == "buscar_web":
        return _t.buscar_web(args.get("query", ""))

    # --- Analizar pantalla ---
    if nombre == "analizar_pantalla":
        return _t.analizar_pantalla(args.get("pregunta", "¿Qué hay en esta pantalla?"))

    # --- Calendario ---
    if nombre == "calendario_hoy":
        import modules.calendario as _cal
        return _cal.ver_eventos_hoy()

    if nombre == "crear_evento":
        import modules.calendario as _cal
        return _cal.crear_evento(
            args.get("titulo", "Evento"),
            args.get("cuando", ""),
            args.get("duracion_min", 60),
        )

    return f"No sé cómo ejecutar '{nombre}'."
