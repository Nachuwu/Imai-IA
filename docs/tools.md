# Referencia de herramientas — Imai

Imai tiene 38 herramientas disponibles. Algunas se ejecutan directamente con regex (fast path, sin llamar al LLM); el resto pasan por Claude que decide cuál usar según el contexto.

---

## Control de sistema

### `volumen`
Controla el volumen del sistema.

| Ejemplo | Efecto |
|---------|--------|
| "sube el volumen" | +10% |
| "baja el volumen" | −10% |
| "pon el volumen al 40" | Establece 40% |
| "silencia" | Mute |
| "activa el sonido" | Desmute |
| "¿a cuánto está el volumen?" | Consulta el nivel actual |

### `brillo`
Controla el brillo de la pantalla.

| Ejemplo | Efecto |
|---------|--------|
| "sube el brillo" | +10% |
| "baja el brillo" | −10% |
| "pon el brillo al 60" | Establece 60% |
| "¿cuánto brillo tengo?" | Consulta el nivel actual |

### `control_pc`
Controla el estado del PC. Las acciones destructivas (apagar, reiniciar, suspender) piden confirmación en voz.

| Ejemplo | Efecto |
|---------|--------|
| "apaga el PC" | Apagado inmediato (pide confirmar) |
| "reinicia el PC" | Reinicio (pide confirmar) |
| "suspende el PC" | Suspende (pide confirmar) |
| "bloquea la pantalla" | Bloqueo inmediato |
| "cancela el apagado" | Cancela `shutdown /a` |

### `ventana`
Controla ventanas abiertas en el escritorio.

| Ejemplo | Efecto |
|---------|--------|
| "minimiza la ventana" | Minimiza la ventana activa |
| "maximiza chrome" | Maximiza Chrome |
| "restaura la ventana" | Restaura tamaño anterior |
| "enfoca el bloc de notas" | Trae al frente |
| "¿qué ventanas tengo abiertas?" | Lista todas |

---

## Aplicaciones

### `abrir_app`
Abre aplicaciones instaladas.

| Ejemplo |
|---------|
| "abre chrome" |
| "abre spotify" |
| "abre el bloc de notas" |
| "lanza visual studio code" |

### `cerrar_app`
Cierra aplicaciones en ejecución.

| Ejemplo |
|---------|
| "cierra chrome" |
| "cierra spotify" |
| "mata el bloc de notas" |

---

## Mouse y teclado (`control_input`)

Una sola herramienta con varias acciones.

### Escribir texto
| Ejemplo | Efecto |
|---------|--------|
| "escribe hola mundo" | Teclea el texto en la app activa |

### Teclas y combinaciones
| Ejemplo | Efecto |
|---------|--------|
| "presiona enter" | Pulsa Enter |
| "presiona control c" | Copia |
| "presiona alt f4" | Cierra ventana |
| "presiona tab" | Tabulador |

### Scroll
| Ejemplo | Efecto |
|---------|--------|
| "haz scroll abajo" | Baja la página |
| "sube tres páginas" | Scroll arriba ×3 |

### Clic por coordenadas
| Ejemplo | Efecto |
|---------|--------|
| "haz clic en 500, 300" | Clic en las coordenadas X=500 Y=300 |

### Clic por texto (Vision)
Busca visualmente el texto en pantalla usando Ctrl+F y Claude Vision.

| Ejemplo | Efecto |
|---------|--------|
| "haz clic en Aceptar" | Localiza y hace clic en el botón |
| "haz clic en Iniciar sesión" | Localiza el texto y hace clic |

> Si pyautogui se descontrola, mueve el mouse a la esquina superior izquierda para abortarlo.

---

## Modo dictar

No es una tool — es un modo especial activado con la frase de inicio.

| Frase | Efecto |
|-------|--------|
| "empieza a dictar" | Activa modo dictar |
| "para de dictar" | Sale del modo dictar |

En modo dictar todo lo que digas se escribe en la aplicación activa. Puedes decir símbolos:

| Dices | Se escribe |
|-------|-----------|
| "punto" | `.` |
| "coma" | `,` |
| "nueva línea" | Enter |
| "dos puntos" | `:` |
| "punto y coma" | `;` |
| "abre paréntesis" | `(` |
| "cierra paréntesis" | `)` |
| "signo de interrogación" | `?` |
| "signo de exclamación" | `!` |
| "guión" | `-` |

---

## Música y medios

### `spotify`
Controla la reproducción de Spotify.

| Ejemplo |
|---------|
| "siguiente canción" |
| "canción anterior" |
| "pausa la música" |
| "¿qué está sonando?" |

### `historial_spotify`
Muestra canciones escuchadas recientemente.

| Ejemplo |
|---------|
| "¿qué canciones estuve escuchando?" |
| "muéstrame el historial de Spotify" |

### `buscar_youtube`
Busca y reproduce en YouTube.

| Ejemplo |
|---------|
| "pon una canción de Bad Bunny en YouTube" |
| "busca tutoriales de Python en YouTube" |

---

## Web y navegación

### `abrir_sitio`
Abre sitios conocidos directamente.

Sitios disponibles: YouTube, Google, Gmail, GitHub, Netflix, Spotify, Twitch, Reddit, Instagram, Facebook, WhatsApp, Wikipedia, Twitter.

| Ejemplo |
|---------|
| "abre YouTube" |
| "abre GitHub" |
| "abre WhatsApp" |

### `buscar_google`
Busca en Google.

| Ejemplo |
|---------|
| "busca recetas de pasta en Google" |
| "googlea qué es la fusión nuclear" |

### `buscar_web`
Busca en internet y devuelve una respuesta directa (DuckDuckGo Instant Answer).

| Ejemplo |
|---------|
| "¿qué es la fotosíntesis?" |
| "¿quién ganó el último mundial?" |
| "busca qué es un transformer en IA" |

### `leer_url`
Lee y resume el contenido de una página web. Si hay un navegador activo, captura la URL automáticamente.

| Ejemplo | Efecto |
|---------|--------|
| "léeme esto" | Resume la página activa |
| "de qué trata esto" | Resumen general |
| "¿qué dice aquí sobre los precios?" | Responde pregunta específica |
| "resume esta página" | Resumen de la página activa |
| "léeme [URL]" | Lee una URL específica |

Navegadores soportados: Chrome, Firefox, Edge, Opera, Brave.

---

## Información

### `hora` / `fecha`
| Ejemplo |
|---------|
| "¿qué hora es?" |
| "¿qué día es hoy?" |
| "¿qué fecha tenemos?" |

### `clima`
| Ejemplo |
|---------|
| "¿cómo está el clima en Santiago?" |
| "¿va a llover hoy?" |
| "temperatura en Buenos Aires" |

### `calcular`
| Ejemplo |
|---------|
| "¿cuánto es 20% de 350?" |
| "calcula 1500 dividido 7" |
| "¿cuánto es 45 por 13?" |

### `portapapeles`
| Ejemplo |
|---------|
| "¿qué tengo copiado?" |
| "lee el portapapeles" |

### `buscar_archivo`
| Ejemplo |
|---------|
| "busca el archivo presupuesto" |
| "¿dónde está el archivo informe?" |

---

## Visión

### `captura_pantalla`
| Ejemplo |
|---------|
| "toma una captura de pantalla" |
| "screenshot" |

### `analizar_pantalla`
Toma una captura y la analiza con Claude Vision.

| Ejemplo |
|---------|
| "¿qué hay en pantalla?" |
| "describe lo que estoy viendo" |
| "¿qué dice ese mensaje de error?" |
| "¿qué código es ese?" |

### `ver_camara`
Captura un frame de la webcam y analiza a la persona.

| Ejemplo |
|---------|
| "¿cómo estoy?" |
| "¿parezco cansado?" |
| "¿qué ropa tengo puesta?" |

### `describir_entorno`
Captura un frame de la webcam y analiza el entorno.

| Ejemplo |
|---------|
| "¿qué hay en mi escritorio?" |
| "¿qué ves detrás de mí?" |
| "describe la habitación" |

---

## Organización

### `timer`
| Ejemplo |
|---------|
| "pon un timer de 5 minutos" |
| "alarma en 30 segundos" |
| "avísame en 2 horas" |
| "cancela el timer" |

### `recordatorio`
Recordatorio puntual (fecha y hora específica). APScheduler lo lanza aunque Imai no esté activo escuchando.

| Ejemplo |
|---------|
| "recuérdame tomar agua mañana a las 8" |
| "recuérdame llamar al médico el viernes a las 10" |

### `alarma_recurrente`
Alarma que se repite en un horario fijo.

| Ejemplo | Frecuencia |
|---------|-----------|
| "ponme una alarma todos los días a las 7" | Diario |
| "alarma de lunes a viernes a las 8" | Entre semana |
| "alarma los sábados a las 10" | Sábados |

### `listar_recordatorios`
| Ejemplo |
|---------|
| "¿qué recordatorios tengo?" |
| "¿qué alarmas tengo programadas?" |

### `cancelar_recordatorio`
Cancela el último recordatorio creado.

| Ejemplo |
|---------|
| "cancela el último recordatorio" |
| "quita la alarma" |

### `no_molestar`
Silencia el micrófono temporalmente.

| Ejemplo |
|---------|
| "silencio por 10 minutos" |
| "modo no molestar por media hora" |
| "desactiva el micro por 5 minutos" |

---

## Memoria

### `guardar_memoria`
Guarda hechos, preferencias o datos varios.

| Ejemplo |
|---------|
| "recuerda que me gusta el café negro" |
| "anota que tengo perro, se llama Coco" |
| "guarda que trabajo hasta las 18:00" |

### `guardar_perfil`
Guarda datos estructurados del perfil (nombre, edad, trabajo, ciudad, etc.).

| Ejemplo |
|---------|
| "me llamo Ignacio" |
| "tengo 25 años" |
| "trabajo de desarrollador" |
| "vivo en Santiago" |

### `actualizar_memoria`
Actualiza un dato ya guardado.

| Ejemplo |
|---------|
| "ahora tengo 26 años" |
| "cambié de trabajo, ahora soy diseñador" |
| "me mudé a Valparaíso" |

### `buscar_memoria`
Búsqueda semántica sobre todo lo que Imai recuerda.

| Ejemplo |
|---------|
| "¿qué recuerdas sobre mí?" |
| "¿recuerdas mis gustos?" |
| "¿qué sabes sobre mis mascotas?" |

---

## Gmail

> Requiere `GMAIL_ENABLED=1` y credenciales OAuth configuradas.

### `leer_correos`
| Ejemplo |
|---------|
| "léeme los últimos correos" |
| "¿tengo correos nuevos?" |
| "léeme los 3 últimos emails" |

### `enviar_correo`
Pide confirmación en voz antes de enviar.

| Ejemplo |
|---------|
| "manda un correo a fulano@gmail.com asunto hola mensaje probando" |
| "envía un email a mi jefe con asunto reunión y dile que no puedo asistir" |

---

## Google Calendar

> Requiere `GOOGLE_CALENDAR_ENABLED=1` y credenciales OAuth configuradas.

### `calendario_hoy`
| Ejemplo |
|---------|
| "¿qué tengo hoy?" |
| "¿tengo algo agendado?" |
| "muéstrame mis eventos de hoy" |

### `crear_evento`
| Ejemplo |
|---------|
| "agéndame dentista el viernes a las 10" |
| "crea un evento reunión mañana a las 3 de la tarde" |
| "agenda almuerzo el lunes al mediodía" |

---

## Alertas proactivas

Estas no son herramientas que el usuario invoca — Imai las ejecuta solo en segundo plano.

| Alerta | Frecuencia | Qué hace |
|--------|-----------|----------|
| **Resumen diario** | 22:00 (cron) | Habla el clima del día, eventos de Calendar, recordatorios pendientes y número de interacciones |
| **Clima adverso** | Cada hora | Si el tiempo cambia a lluvia, nieve o tormenta, avisa en voz. Reset automático cuando mejora. |
| **Correos importantes** | Cada 15 min | Revisa Gmail, Claude juzga si hay algo urgente y avisa. No repite el mismo correo. |
| **Inactividad** | Cada 5 min | Si llevas más de 45 minutos sin hablar, sugiere levantarte o tomar agua. |

El estado de cada alerta se persiste en `data/proactivo_estado.json` — sobrevive reinicios.

---

## Comandos encadenados

Imai puede ejecutar múltiples comandos en una sola frase, separados por "y", "luego", "después", "también" o "además":

```
"sube el volumen y abre chrome"
"pausa la música y después pon un timer de 5 minutos"
"toma una captura y dime qué hay en pantalla"
"cierra spotify y abre YouTube"
```
