(() => {
  "use strict";

  const INTERVALO_MIN = 15;
  const ORDEN = ["todos", "modelos", "producto", "empresas", "investigacion", "politica", "hardware"];
  const NOMBRES = {
    todos: "Todo",
    modelos: "Modelos",
    producto: "Producto",
    empresas: "Empresas",
    investigacion: "Investigación",
    politica: "Política",
    hardware: "Hardware"
  };
  const VIGENCIA_NUEVO = 30 * 60 * 1000;
  const MAX_SALUD = 40;

  const $ = (id) => document.getElementById(id);
  const raiz = document.documentElement;

  const els = {
    estado: $("estado"),
    estadoTxt: $("estadoTxt"),
    reloj: $("reloj"),
    cargaTxt: $("cargaTxt"),
    btnActualizar: $("btnActualizar"),
    btnTema: $("btnTema"),
    aviso: $("aviso"),
    pestanas: $("pestanas"),
    buscar: $("buscar"),
    btnLimpiar: $("btnLimpiar"),
    portada: $("portada"),
    resumen: $("resumen"),
    btnNuevo: $("btnNuevo"),
    rejilla: $("rejilla"),
    entidades: $("entidades"),
    fuentes: $("fuentes"),
    sistema: $("sistema"),
    pista: $("pista"),
    pieMono: $("pieMono")
  };

  let datos = null;
  let todos = [];
  let filtro = "todos";
  let consulta = "";
  let consultaNorm = "";
  const entidadesOn = new Set();
  const vistos = new Set();
  const nuevosEn = new Map();
  let pendientes = 0;
  let cuentaAtras = INTERVALO_MIN * 60;
  let cargando = false;
  let origen = "";

  const esc = (s) =>
    String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );

  const norm = (s) =>
    String(s == null ? "" : s)
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "");

  function mapaNorm(texto) {
    let salida = "";
    const mapa = [];
    for (let i = 0; i < texto.length; i++) {
      const n = norm(texto[i]);
      for (let k = 0; k < n.length; k++) {
        salida += n[k];
        mapa.push(i);
      }
    }
    return { salida, mapa };
  }

  function resaltar(texto) {
    const limpio = esc(texto);
    if (!consultaNorm || consultaNorm.length < 2) return limpio;
    const { salida, mapa } = mapaNorm(texto);
    const aguja = consultaNorm;
    if (salida.indexOf(aguja) === -1) return limpio;
    let res = "";
    let i = 0;
    let idx = salida.indexOf(aguja);
    while (idx !== -1) {
      const ini = mapa[idx];
      const fin = mapa[idx + aguja.length - 1] + 1;
      res += esc(texto.slice(i, ini)) + "<mark>" + esc(texto.slice(ini, fin)) + "</mark>";
      i = fin;
      idx = salida.indexOf(aguja, idx + aguja.length);
    }
    res += esc(texto.slice(i));
    return res;
  }

  function relativo(iso) {
    const t = new Date(iso).getTime();
    if (!iso || isNaN(t)) return "";
    const min = Math.floor((Date.now() - t) / 60000);
    if (min < 1) return "ahora";
    if (min < 60) return "hace " + min + " min";
    const h = Math.floor(min / 60);
    if (h < 24) return "hace " + h + " h";
    const d = Math.floor(h / 24);
    if (d < 7) return "hace " + d + (d === 1 ? " día" : " días");
    return new Date(t).toLocaleDateString("es-MX", { day: "numeric", month: "short" });
  }

  const completo = (iso) => {
    const t = new Date(iso);
    return isNaN(t.getTime()) ? "" : t.toLocaleString("es-MX", { dateStyle: "medium", timeStyle: "short" });
  };

  function mins(iso) {
    const t = new Date(iso).getTime();
    return isNaN(t) ? null : Math.max(0, Math.round((Date.now() - t) / 60000));
  }

  function setNivel(nivel, texto) {
    els.estado.dataset.nivel = nivel;
    els.estadoTxt.textContent = texto;
  }

  function pintarPestanas() {
    const conteo = Object.assign({ todos: todos.length }, (datos && datos.by_category) || {});
    els.pestanas.innerHTML = ORDEN.map((c) => {
      const n = conteo[c] || 0;
      if (c !== "todos" && n === 0 && c !== filtro) return "";
      return (
        '<button class="pest" role="tab" type="button" data-cat="' + c + '" aria-selected="' +
        (c === filtro) + '">' + NOMBRES[c] + ' <span class="n">' + n + "</span></button>"
      );
    }).join("");
  }

  function coincide(n) {
    if (filtro !== "todos" && n.category !== filtro) return false;
    if (entidadesOn.size) {
      if (!n.entity || !entidadesOn.has(n.entity)) return false;
    }
    if (consultaNorm) {
      const t = norm(
        n.title + " " + (n.summary || "") + " " + n.source + " " + (n.entity || "") + " " + n.category
      );
      if (t.indexOf(consultaNorm) === -1) return false;
    }
    return true;
  }

  const hayFiltros = () => filtro !== "todos" || !!consultaNorm || entidadesOn.size > 0;

  function htmlPortada(n) {
    const cat = esc(NOMBRES[n.category] || n.category);
    const derecha = n.image
      ? '<figure class="medio-img"><img src="' + esc(n.image) + '" alt="" loading="lazy" decoding="async" />' +
        (n.source ? '<figcaption class="sello">' + esc(n.source) + "</figcaption>" : "") +
        "</figure>"
      : '<aside class="ficha"><h3>Ficha</h3><dl>' +
        "<dt>Categoría</dt><dd>" + cat + "</dd>" +
        "<dt>Publicado</dt><dd>" + relativo(n.published) + "</dd>" +
        "<dt>Fuente</dt><dd>" + esc(n.feed) + "</dd>" +
        (n.entity ? "<dt>Entidad</dt><dd>" + esc(n.entity) + "</dd>" : "") +
        "</dl>" +
        ((n.also || []).length
          ? '<p class="otras">También en ' +
            n.also
              .map((a) => '<a href="' + esc(a.link) + '" target="_blank" rel="noopener">' + esc(a.source) + "</a>")
              .join(" · ") +
            "</p>"
          : "") +
        "</aside>";
    return (
      '<div class="cuerpo">' +
        '<span class="giro">' + cat + (n.entity ? " · " + esc(n.entity) : "") + "</span>" +
        '<h2><a href="' + esc(n.link) + '" target="_blank" rel="noopener">' + resaltar(n.title) + "</a></h2>" +
        (n.summary ? '<p class="res">' + resaltar(n.summary) + "</p>" : "") +
        '<div class="pie"><span class="medio">' + esc(n.source || n.feed) + "</span>" +
        (n.feed && n.feed !== n.source ? "<span>" + esc(n.feed) + "</span>" : "") +
        '<time data-iso="' + esc(n.published) + '" title="' + esc(completo(n.published)) + '">' + relativo(n.published) + "</time>" +
        "</div>" +
      "</div>" + derecha
    );
  }

  function htmlTarjeta(n, i) {
    const reciente = nuevosEn.has(n.link) && Date.now() - nuevosEn.get(n.link) < VIGENCIA_NUEVO;
    const medios = (n.also || []).length;
    return (
      '<article class="tarjeta" style="--i:' + Math.min(i, 14) + '">' +
        '<div class="tarjeta-cab"><span class="categoria">' + esc(NOMBRES[n.category] || n.category) + "</span>" +
          (n.entity ? '<span class="entidad">' + esc(n.entity) + "</span>" : "") +
          '<span class="sellos">' +
          (reciente ? '<span class="sello-nuevo">nuevo</span>' : "") +
          (medios ? '<span class="sello-medios" title="Cubierta por otros medios">+' + medios + "</span>" : "") +
          "</span></div>" +
        '<h3><a href="' + esc(n.link) + '" target="_blank" rel="noopener">' + resaltar(n.title) + "</a></h3>" +
        (n.summary ? '<p class="res">' + resaltar(n.summary) + "</p>" : "") +
        '<div class="pie"><span class="medio">' + esc(n.source || n.feed) + "</span>" +
        '<time data-iso="' + esc(n.published) + '" title="' + esc(completo(n.published)) + '">' + relativo(n.published) + "</time></div>" +
      "</article>"
    );
  }

  function pintarPortada() {
    const lead = datos && datos.lead;
    if (!lead || hayFiltros() || !coincide(lead)) {
      els.portada.classList.remove("visible");
      els.portada.innerHTML = "";
      return;
    }
    els.portada.innerHTML = htmlPortada(lead);
    els.portada.classList.add("visible");
    els.portada.classList.toggle("sin-imagen", !lead.image);
  }

  function pintarRejilla() {
    const lead = datos && datos.lead;
    const base = lead && !hayFiltros() ? todos.filter((n) => n !== lead) : todos;
    const lista = base.filter(coincide);

    if (hayFiltros()) {
      const activos = [];
      if (filtro !== "todos") activos.push(NOMBRES[filtro]);
      if (consultaNorm) activos.push('“' + consulta + '”');
      if (entidadesOn.size) activos.push([...entidadesOn].join(" + "));
      els.resumen.innerHTML =
        lista.length + " de " + todos.length + " · filtro " + activos.join(" · ");
    } else {
      const hoy = todos.filter((n) => mins(n.published) !== null && mins(n.published) < 1440).length;
      els.resumen.innerHTML =
        "<b>" + todos.length + "</b> noticias · " + hoy + " de las últimas 24 h · " +
        "se revisa sola cada " + INTERVALO_MIN + " min";
    }

    if (pendientes > 0) {
      els.btnNuevo.hidden = false;
      els.btnNuevo.textContent = "↑ " + pendientes + (pendientes === 1 ? " nueva" : " nuevas");
    } else {
      els.btnNuevo.hidden = true;
    }

    if (!lista.length) {
      els.rejilla.innerHTML =
        '<div class="vacio"><h3>Nada que coincida</h3><p>Prueba con otra palabra o quita los filtros.</p></div>';
      return;
    }
    els.rejilla.innerHTML = lista.map(htmlTarjeta).join("");
  }

  function pintarEntidades() {
    const lista = (datos && datos.top_entities) || [];
    if (!lista.length) {
      els.entidades.innerHTML = '<p class="nota" style="margin:0">Sin datos de entidades todavía.</p>';
      return;
    }
    els.entidades.innerHTML = lista
      .map(
        (e) =>
          '<button class="chip" type="button" data-ent="' + esc(e.name) + '" aria-pressed="' +
          entidadesOn.has(e.name) + '">' + esc(e.name) + ' <span class="n">' + e.count + "</span></button>"
      )
      .join("");
  }

  function pintarFuentes() {
    const salud = (datos && datos.health) || [];
    if (!salud.length) {
      els.fuentes.innerHTML = '<li class="salud"><span class="nombre">Sin datos de salud de fuentes.</span></li>';
      return;
    }
    els.fuentes.innerHTML = salud
      .slice(0, MAX_SALUD)
      .map(
        (s) =>
          '<li><i class="' + (s.ok ? "ok" : "mal") + '"></i><span class="nombre">' + esc(s.name) + "</span>" +
          (s.ok
            ? '<span class="cifra">' + s.count + "</span>"
            : '<span class="motivo">' + esc(s.error || "sin datos") + "</span>") +
          "</li>"
      )
      .join("");
  }

  function pintarSistema() {
    if (!datos) {
      els.sistema.innerHTML = "";
      return;
    }
    const gen = datos.generated_at;
    const edad = mins(gen);
    const d = new Date(gen);
    const descarga = isNaN(d.getTime())
      ? "—"
      : d.toLocaleDateString("es-MX", { day: "numeric", month: "short" }) +
        " · " +
        d.toLocaleTimeString("es-MX", { hour: "2-digit", minute: "2-digit", hour12: false });
    const agrupadas = datos.grouped || 0;
    const filas = [
      ["Última descarga", descarga],
      ["Antigüedad", edad === null ? "—" : edad < 60 ? edad + " min" : Math.round(edad / 60) + " h"],
      ["Fuentes", "<b>" + (datos.feeds_ok || 0) + "</b> / " + (datos.feeds_total || 0)],
      ["Agrupadas", agrupadas + (agrupadas === 1 ? " duplicada" : " duplicadas")],
      ["Duración", (datos.took_sec || 0) + " s"],
      ["Próxima revisión", '<span id="dCuenta">' + cuentaAtras + "</span>"]
    ];
    els.sistema.innerHTML = filas
      .map((f) => "<dt>" + f[0] + "</dt><dd>" + f[1] + "</dd>")
      .join("");

    els.pieMono.textContent =
      todos.length + " noticias · " + (datos.feeds_ok || 0) + "/" + (datos.feeds_total || 0) + " fuentes · " +
      (origen || "local") + " · generado " + (gen ? new Date(gen).toLocaleTimeString("es-MX", { hour: "2-digit", minute: "2-digit" }) : "—");

    const viejo = edad !== null && edad > 45;
    if (viejo && !datos.stale) {
      mostrarAviso(
        "Los datos tienen " + Math.round(edad / 60) + " h. Doble clic en <b>actualizar.bat</b> para refrescar ahora."
      );
    } else if (datos.stale) {
      mostrarAviso("Sin noticias nuevas en la última revisión: se conserva el archivo anterior.");
    } else {
      ocultarAviso();
    }
  }

  function mostrarAviso(html) {
    els.aviso.innerHTML = html;
    els.aviso.hidden = false;
  }
  function ocultarAviso() {
    els.aviso.hidden = true;
    els.aviso.innerHTML = "";
  }

  function pintar() {
    pintarPestanas();
    pintarPortada();
    pintarRejilla();
    pintarEntidades();
    pintarFuentes();
    pintarSistema();
  }

  function aplicarDatos(d) {
    if (!d || !Array.isArray(d.items)) return;
    datos = d;
    const lista = [];
    if (d.lead) lista.push(d.lead);
    for (const n of d.items) if (n && n.title && n.link) lista.push(n);

    const primeraCarga = vistos.size === 0;
    const nuevosLinks = new Set();
    for (const n of lista) {
      if (!primeraCarga && !vistos.has(n.link)) nuevosLinks.add(n.link);
      vistos.add(n.link);
    }

    if (primeraCarga) {
      pendientes = 0;
      nuevosEn.clear();
    } else {
      const ahora = Date.now();
      let cuenta = 0;
      for (const l of nuevosLinks) {
        const n = lista.find((x) => x.link === l);
        const edad = n ? mins(n.published) : null;
        if (edad !== null && edad < 180) {
          nuevosEn.set(l, ahora);
          cuenta++;
        }
      }
      nuevosEn.forEach((marca, l) => {
        if (ahora - marca > VIGENCIA_NUEVO) nuevosEn.delete(l);
      });
      pendientes = cuenta;
    }

    todos = lista;
    cuentaAtras = INTERVALO_MIN * 60;
    setNivel("ok", lista.length + " en vivo");
    pintar();
  }

  function aplicarLocal() {
    const emb = window.PULSO_DATA;
    if (emb && Array.isArray(emb.items)) {
      origen = "archivo local";
      aplicarDatos(emb);
      return true;
    }
    return false;
  }

  function fallo() {
    setNivel("error", "sin datos");
    origen = "";
    datos = null;
    todos = [];
    ocultarAviso();
    els.portada.classList.remove("visible");
    els.portada.innerHTML = "";
    els.rejilla.innerHTML =
      '<div class="vacio"><h3>No hay datos todavía</h3><p>Doble clic en <code>actualizar.bat</code> para descargar ' +
      "las noticias, o abre <code>servidor.bat</code> y entra por <code>localhost</code>.</p></div>";
    els.resumen.textContent = "";
    pintarPestanas();
    pintarEntidades();
    pintarFuentes();
    pintarSistema();
  }

  async function cargar(silencioso) {
    if (cargando) return;
    cargando = true;
    els.btnActualizar.classList.add("cargando");
    els.btnActualizar.disabled = true;
    if (!silencioso) setNivel("carga", "actualizando");
    try {
      const res = await fetch("data/news.json?t=" + Date.now(), { cache: "no-store" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const d = await res.json();
      origen = "servidor";
      aplicarDatos(d);
    } catch (e) {
      if (!aplicarLocal()) fallo();
      else setNivel("ok", todos.length + " en vivo");
    } finally {
      cargando = false;
      els.btnActualizar.classList.remove("cargando");
      els.btnActualizar.disabled = false;
    }
  }

  function actualizarTiempos() {
    document.querySelectorAll("time[data-iso]").forEach((t) => {
      t.textContent = relativo(t.dataset.iso);
    });
  }

  function temaGuardado() {
    try {
      return localStorage.getItem("pulsoia-tema");
    } catch (e) {
      return null;
    }
  }

  function aplicarTema(t) {
    raiz.dataset.tema = t;
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", t === "dia" ? "#f7f6f3" : "#0b0b0c");
    try {
      localStorage.setItem("pulsoia-tema", t);
    } catch (e) {}
  }

  function iniciarTema() {
    const guardado = temaGuardado();
    const preferido = window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches ? "dia" : "noche";
    aplicarTema(guardado || preferido);
    els.btnTema.addEventListener("click", () => {
      aplicarTema(raiz.dataset.tema === "dia" ? "noche" : "dia");
    });
  }

  function eventos() {
    els.pestanas.addEventListener("click", (e) => {
      const b = e.target.closest(".pest");
      if (!b) return;
      filtro = b.dataset.cat;
      pintar();
    });

    let temp = null;
    els.buscar.addEventListener("input", (e) => {
      const v = e.target.value;
      els.btnLimpiar.hidden = !v;
      clearTimeout(temp);
      temp = setTimeout(() => {
        consulta = v.trim();
        consultaNorm = norm(consulta);
        pintar();
      }, 160);
    });

    const limpiarBusqueda = () => {
      els.buscar.value = "";
      els.btnLimpiar.hidden = true;
      consulta = "";
      consultaNorm = "";
      pintar();
    };
    els.btnLimpiar.addEventListener("click", () => {
      limpiarBusqueda();
      els.buscar.focus();
    });

    els.entidades.addEventListener("click", (e) => {
      const b = e.target.closest(".chip");
      if (!b) return;
      const n = b.dataset.ent;
      if (entidadesOn.has(n)) entidadesOn.delete(n);
      else entidadesOn.add(n);
      pintar();
    });

    els.btnActualizar.addEventListener("click", () => cargar(false));

    els.btnNuevo.addEventListener("click", () => {
      pendientes = 0;
      pintar();
      window.scrollTo({ top: 0, behavior: "smooth" });
    });

    document.addEventListener("keydown", (e) => {
      const activo = document.activeElement;
      const enCampo = !!activo && /^(INPUT|TEXTAREA|SELECT)$/.test(activo.tagName);
      if (e.key === "/" && !enCampo) {
        e.preventDefault();
        els.buscar.focus();
        els.buscar.select();
      } else if (e.key === "Escape") {
        if (enCampo) limpiarBusqueda();
        if (activo && activo.blur) activo.blur();
      }
    });

    document.addEventListener("visibilitychange", () => {
      if (document.hidden) return;
      const edad = datos ? mins(datos.generated_at) : null;
      if (cargando) return;
      if (edad === null || edad >= INTERVALO_MIN) cargar(true);
    });
  }

  function reloj() {
    const ahora = new Date();
    els.reloj.textContent = ahora.toLocaleTimeString("es-MX", { hour12: false });
    if (cargando) {
      els.cargaTxt.textContent = "descargando…";
      return;
    }
    const mm = String(Math.floor(Math.max(0, cuentaAtras) / 60)).padStart(2, "0");
    const ss = String(Math.max(0, cuentaAtras) % 60).padStart(2, "0");
    els.cargaTxt.textContent = "revisa en " + mm + ":" + ss;
    const celda = document.getElementById("dCuenta");
    if (celda) celda.textContent = mm + ":" + ss;
  }

  function arrancar() {
    iniciarTema();
    eventos();
    reloj();
    setInterval(reloj, 1000);
    setInterval(actualizarTiempos, 30000);
    setInterval(() => {
      if (cargando || document.hidden) return;
      cuentaAtras--;
      if (cuentaAtras <= 0) {
        cuentaAtras = INTERVALO_MIN * 60;
        cargar(true);
      }
    }, 1000);
    cargar(false);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", arrancar);
  } else {
    arrancar();
  }
})();
