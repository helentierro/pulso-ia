================================================================
 PULSO IA - noticias de inteligencia artificial en vivo
================================================================

QUE ES
 Una pagina que junta las ultimas noticias de IA de 24 fuentes
 RSS (OpenAI, Google DeepMind, NVIDIA, TechCrunch, arXiv,
 The Verge, The Decoder, MIT Tech Review, Google News, etc.),
 las limpia, las clasifica en 6 categorias, agrupa las que
 cuentan la misma historia y las muestra ordenadas por fecha.
 Se actualiza sola una vez al dia de forma automatica.

ARCHIVOS
 index.html ............ la pagina (doble clic y listo)
 styles.css ............ diseno (tema noche y dia)
 app.js ................ filtros, busqueda, reloj, recarga
 fetch_news.py ......... descarga los RSS y genera los datos
 actualizar.bat ........ descarga las noticias y abre la web
 actualizar_silencioso.bat  para Tarea Programada (sin ventana)
 servidor.bat .......... abre la web en un servidor local
 data/news.json ........ datos que lee la pagina servida
 data/news.js .......... mismos datos para abrir con doble clic
 auto_update.log ....... registro de las actualizaciones

COMO USARLO
 1. Doble clic en actualizar.bat   (necesita internet + Python)
 2. Se abre index.html en tu navegador
 3. Cada 15 min la pagina se recarga sola; el boton "Actualizar"
    fuerza una revision inmediata de los datos

 Si prefieres servidor local: doble clic en servidor.bat
 (abre http://localhost:8765 - es mas fluido y sin bloqueos)

REPARTO EN CATEGORIAS
 Modelos ....... GPT, Claude, Gemini, Llama y similares
 Producto ...... apps, funciones y lanzamientos de herramientas
 Empresas ...... inversion, acuerdos, empleo y salidas
 Investigacion . papers, estudios, benchmarks, arXiv
 Politica ...... regulacion, leyes, demandas, seguridad
 Hardware ...... GPUs, chips, centros de datos

 ATAJOS DE TECLADO
 / .............. ir al buscador
 Escape ......... limpiar la busqueda
click en chip ... filtrar por OpenAI, Nvidia, Anthropic...

CAMBIAR EL TEMA (NOCHE / DIA)
 El boton de la luna alterna tema noche / dia.
 La preferencia se guarda en el navegador.

COMO SE AUTOMATIZA (Windows)
 1. Abre "Programador de tareas" (Task Scheduler)
 2. Crear tarea basica -> activar -> disparador: cada 15 minutos
 3. Accion: "Iniciar programa"
    Programa:  D:\DE Dani\PULSO IA\actualizar_silencioso.bat
 4. Listo: data/news.json se refresca solo, la pagina lo detecta

  Esto es solo para la copia de tu PC. La version publicada en GitHub
  se actualiza por su cuenta con un workflow: una vez al dia y no hace
  falta el PC encendido. Para forzarlo a mano:
  GitHub -> pestana Actions -> "Actualizar noticias" -> Run workflow.
  Si un dia un medio cambia su RSS, el panel de salud marcara menos de
  24 feeds. El resto sigue funcionando con los datos que ya havia.

NOTAS
 - Solo se muestra titular, resumen y enlace al medio original.
   No se copia el articulo completo.
 - Las fechas y el orden dependen de cada medio: hay feeds que
   publican una vez por semana.
 - El buscador ignora acentos: "regulacion" encuentra "regulación".
 - Si no hay internet, se conserva el archivo anterior y la pagina
   avisa que los datos pueden estar viejos.
 - No es asesoria financiera ni de inversion.

AJUSTAR FUENTES
 Edita la lista FUENTES al inicio de fetch_news.py. Cada linea es:
   (nombre, url_rss, categoria_por_defecto, prioridad, tipo, horas_max)
 Prioridad alta (4) =peso en la eleccion del titular.
 Si un feed falla, la pagina lo marca en rojo en el panel "Fuentes".
