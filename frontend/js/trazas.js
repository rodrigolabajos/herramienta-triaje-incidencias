// trazas.js — VISOR XML AGRUPADO POR SECCIONES
// =============================================
// ✅ Padres = cabeceras de sección coloreadas
// ✅ Hijos = filas campo/valor dentro de la sección
// ✅ Sin indentación en cascada — todo limpio y compacto
// ✅ Soporta XML escapado y doble escapado
// ✅ Tab "Plano" conservado
// ✅ Búsqueda en panel Visual

const trazasOverlay  = document.getElementById("trazasOverlay");
const trazasBody     = document.getElementById("trazasBody");
const trazasModalId  = document.getElementById("trazasModalId");
const btnTrazasClose = document.getElementById("btnTrazasClose");

let tabActiva = "visual";

/* ── Eventos cierre ──────────────────────────────────────── */

btnTrazasClose.onclick = () => { limpiarBusqueda(); trazasOverlay.classList.add("hidden"); };
trazasOverlay.onclick  = e  => { if (e.target === trazasOverlay) { limpiarBusqueda(); trazasOverlay.classList.add("hidden"); } };
document.addEventListener("keydown", e => { if (e.key === "Escape") { limpiarBusqueda(); trazasOverlay.classList.add("hidden"); } });

/* ── Búsqueda: listeners (el script corre con el DOM ya listo) ── */

document.getElementById("trazasSearchInput").addEventListener("input", function () {
  const q = this.value.trim();
  document.getElementById("trazasSearchClear").classList.toggle("hidden", q === "");
  aplicarBusqueda(q);
});

document.getElementById("trazasSearchClear").addEventListener("click", limpiarBusqueda);
document.getElementById("btnExpandAll").addEventListener("click", () => expandirTodo(true));
document.getElementById("btnCollapseAll").addEventListener("click", () => expandirTodo(false));
document.getElementById("btnCopyPlano").addEventListener("click", copiarPlano);

/* ── Abrir trazas ────────────────────────────────────────── */

async function abrirTrazas(idIncidencia) {
  trazasModalId.textContent = idIncidencia;
  trazasBody.innerHTML = `<div class="trazas-loading">Cargando trazas…</div>`;
  trazasOverlay.classList.remove("hidden");

  tabActiva = "visual";
  document.getElementById("tabVisual").classList.add("active");
  document.getElementById("tabPlano").classList.remove("active");
  document.getElementById("trazasSearchBar").classList.remove("hidden");
  document.getElementById("btnExpandAll").classList.remove("hidden");
  document.getElementById("btnCollapseAll").classList.remove("hidden");
  document.getElementById("btnCopyPlano").classList.add("hidden");
  limpiarBusqueda();

  const r    = await fetch(`${API_BASE}/incidencias/${encodeURIComponent(idIncidencia)}/trazas`);
  const data = await r.json();

  window._trazasContenido = data.trazas || "";
  renderTrazas();
}

/* ── Tabs ────────────────────────────────────────────────── */

function switchTab(tab) {
  tabActiva = tab;
  document.getElementById("tabVisual").classList.toggle("active", tab === "visual");
  document.getElementById("tabPlano").classList.toggle("active",  tab === "plano");

  const barra = document.getElementById("trazasSearchBar");
  const btnExp = document.getElementById("btnExpandAll");
  const btnCol = document.getElementById("btnCollapseAll");
  const btnCpy = document.getElementById("btnCopyPlano");

  if (tab === "visual") {
    barra.classList.remove("hidden");
    btnExp.classList.remove("hidden");
    btnCol.classList.remove("hidden");
    btnCpy.classList.add("hidden");
  } else {
    barra.classList.add("hidden");
    btnExp.classList.add("hidden");
    btnCol.classList.add("hidden");
    btnCpy.classList.remove("hidden");
    limpiarBusqueda();
  }

  renderTrazas();
}

/* ── Render principal ────────────────────────────────────── */

function renderTrazas() {
  const raw = window._trazasContenido;
  if (!raw) { trazasBody.innerHTML = `<div class="trazas-empty">No hay trazas</div>`; return; }

  if (tabActiva === "plano") {
    trazasBody.innerHTML = `<div class="trazas-raw"><pre>${escapeHtml(raw)}</pre></div>`;
    return;
  }

  const texto = normalizarHtml(raw);
  const arbol = parsearXml(texto);

  if (!arbol || arbol.hijos.length === 0) {
    trazasBody.innerHTML = renderLineasPlanas(texto);
    return;
  }

  trazasBody.innerHTML = `<div class="tsec-root">${arbol.hijos.map((n, i) => renderSeccion(n, i, 0)).join("")}</div>`;

  // Colapso
  trazasBody.querySelectorAll(".tsec-toggle").forEach(btn => {
    btn.addEventListener("click", () => {
      const sec  = btn.closest(".tsec-block");
      const body = sec.querySelector(":scope > .tsec-body");
      if (!body) return;
      const collapsed = body.style.display === "none";
      body.style.display = collapsed ? "" : "none";
      btn.textContent = collapsed ? "▾" : "▸";
    });
  });
}

/* ── Parser XML → árbol ──────────────────────────────────── */

function parsearXml(texto) {
  const raiz  = { tag: "__root__", attrs: {}, hijos: [], texto: "" };
  const stack = [raiz];
  const re    = /<([A-Za-z0-9_:-]+)([^>]*)\/?>|<\/[A-Za-z0-9_:-]+>|([^<>]+)/g;
  let m;
  while ((m = re.exec(texto)) !== null) {
    const padre = stack[stack.length - 1];
    if (m[3] !== undefined) {
      const v = m[3].trim();
      if (v) padre.texto = (padre.texto ? padre.texto + " " : "") + v;
    } else if (m[0].startsWith("</")) {
      if (stack.length > 1) stack.pop();
    } else if (m[1]) {
      const nodo = { tag: m[1], attrs: parsearAttrs(m[2] || ""), hijos: [], texto: "" };
      padre.hijos.push(nodo);
      if (!m[0].endsWith("/>")) stack.push(nodo);
    }
  }
  return raiz;
}

function parsearAttrs(str) {
  const attrs = {}, re = /([A-Za-z0-9_:-]+)\s*=\s*"([^"]*)"/g;
  let m;
  while ((m = re.exec(str)) !== null) attrs[m[1]] = m[2];
  return attrs;
}

/* ── Render por secciones ────────────────────────────────── */

const PALETA = [
  { header: "#1e3a8a", light: "#f8faff", border: "#dbe4ff" },
  { header: "#1e40af", light: "#f1f5ff", border: "#c7d2fe" },
  { header: "#0f4c81", light: "#eef6fb", border: "#bdd7ee" },
  { header: "#312e81", light: "#f4f3ff", border: "#dcdafe" },
  { header: "#0f766e", light: "#edfafa", border: "#99e6e2" },
  { header: "#334155", light: "#f8fafc", border: "#cbd5e1" }
];

function renderSeccion(nodo, idx, nivel) {
  const color = PALETA[nivel % PALETA.length];

  const attrsStr = Object.entries(nodo.attrs)
    .map(([k, v]) => `<span class="tsec-attr"><b>${escapeHtml(k)}</b>="${escapeHtml(v)}"</span>`)
    .join(" ");

  const tieneHijos = nodo.hijos.length > 0;
  const tieneTexto = nodo.texto.trim().length > 0;

  if (!tieneHijos && tieneTexto) {
    return `
      <div class="tsec-row">
        <span class="tsec-row-key" style="color:${color.header}">${escapeHtml(nodo.tag)}</span>
        ${attrsStr ? `<span class="tsec-row-attrs">${attrsStr}</span>` : ""}
        <span class="tsec-row-val">${escapeHtml(nodo.texto.trim())}</span>
      </div>`;
  }

  if (!tieneHijos && !tieneTexto && Object.keys(nodo.attrs).length > 0) {
    return `
      <div class="tsec-row">
        <span class="tsec-row-key" style="color:${color.header}">${escapeHtml(nodo.tag)}</span>
        <span class="tsec-row-attrs">${attrsStr}</span>
      </div>`;
  }

  const textoPropio = tieneTexto
    ? `<div class="tsec-row tsec-row--own">
         <span class="tsec-row-key tsec-row-key--own">valor</span>
         <span class="tsec-row-val">${escapeHtml(nodo.texto.trim())}</span>
       </div>`
    : "";

  const contenidoHijos = nodo.hijos.map((h, i) => renderSeccion(h, i, nivel + 1)).join("");

  return `
    <div class="tsec-block" style="--sec-header:${color.header}; --sec-light:${color.light}; --sec-border:${color.border}">
      <div class="tsec-header">
        <button class="tsec-toggle">▾</button>
        <span class="tsec-tag">${escapeHtml(nodo.tag)}</span>
        ${attrsStr ? `<span class="tsec-header-attrs">${attrsStr}</span>` : ""}
        ${tieneHijos ? `<span class="tsec-cnt">${nodo.hijos.length}</span>` : ""}
      </div>
      <div class="tsec-body">
        ${textoPropio}${contenidoHijos}
      </div>
    </div>`;
}

/* ── Fallback ────────────────────────────────────────────── */

function renderLineasPlanas(texto) {
  const lineas = texto.split(/\n/).map(l => l.trim()).filter(Boolean);
  if (!lineas.length) return `<div class="trazas-empty">Sin datos estructurados</div>`;
  return `<div class="tsec-root">${lineas.map(l =>
    `<div class="tsec-row"><span class="tsec-row-val">${escapeHtml(l)}</span></div>`
  ).join("")}</div>`;
}

/* ── Utilidades ──────────────────────────────────────────── */

function normalizarHtml(txt) {
  let prev, cur = txt;
  do { prev = cur; cur = cur.replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">"); }
  while (cur !== prev);
  return cur;
}

function escapeHtml(str) {
  return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

/* ── Búsqueda ────────────────────────────────────────────── */

function limpiarBusqueda() {
  const input = document.getElementById("trazasSearchInput");
  const clear = document.getElementById("trazasSearchClear");
  const count = document.getElementById("trazasSearchCount");
  input.value = "";
  clear.classList.add("hidden");
  count.textContent = "";
  count.classList.remove("no-results");
  aplicarBusqueda("");
}

function aplicarBusqueda(query) {
  const root = trazasBody.querySelector(".tsec-root");
  if (!root) return;

  const count = document.getElementById("trazasSearchCount");

  if (!query) {
    root.querySelectorAll(".tsec-row").forEach(el => {
      el.classList.remove("tsec-hidden");
      el.querySelectorAll(".tsec-match").forEach(m => m.replaceWith(document.createTextNode(m.textContent)));
    });
    root.querySelectorAll(".tsec-block").forEach(el => {
      el.classList.remove("tsec-no-match");
      const body = el.querySelector(":scope > .tsec-body");
      if (!body) return;
      if (body.dataset.searchHidden) {
        body.style.display = "none";
        delete body.dataset.searchHidden;
      } else {
        body.style.display = "";
      }
    });
    count.textContent = "";
    return;
  }

  const q = query.toLowerCase();
  let total = 0;

  // 1. Marcar/ocultar filas hoja
  root.querySelectorAll(".tsec-row").forEach(el => {
    el.querySelectorAll(".tsec-match").forEach(m => m.replaceWith(document.createTextNode(m.textContent)));
    if (el.textContent.toLowerCase().includes(q)) {
      el.classList.remove("tsec-hidden");
      total++;
      resaltarEnElemento(el, q);
    } else {
      el.classList.add("tsec-hidden");
    }
  });

  // 2. Mostrar/ocultar bloques según si tienen contenido visible
  Array.from(root.querySelectorAll(".tsec-block")).reverse().forEach(bloque => {
    const body = bloque.querySelector(":scope > .tsec-body");
    if (!body) return;
    const tieneVisibles = body.querySelector(".tsec-row:not(.tsec-hidden)") ||
                          body.querySelector(".tsec-block:not(.tsec-no-match)");
    if (tieneVisibles) {
      bloque.classList.remove("tsec-no-match");
      if (body.style.display === "none") {
        body.dataset.searchHidden = "1";
        body.style.display = "";
        const btn = bloque.querySelector(".tsec-toggle");
        if (btn) btn.textContent = "▾";
      }
    } else {
      bloque.classList.add("tsec-no-match");
    }
  });

  // 3. Contador
  if (total === 0) {
    count.textContent = "Sin resultados";
    count.classList.add("no-results");
  } else {
    count.textContent = `${total} resultado${total !== 1 ? "s" : ""}`;
    count.classList.remove("no-results");
  }
}

function resaltarEnElemento(el, query) {
  el.querySelectorAll(".tsec-row-key, .tsec-row-val, .tsec-attr").forEach(span => {
    span.childNodes.forEach(nodo => {
      if (nodo.nodeType !== Node.TEXT_NODE) return;
      const texto = nodo.textContent;
      const idx   = texto.toLowerCase().indexOf(query);
      if (idx === -1) return;
      const frag = document.createDocumentFragment();
      frag.appendChild(document.createTextNode(texto.slice(0, idx)));
      const mark = document.createElement("mark");
      mark.className = "tsec-match";
      mark.textContent = texto.slice(idx, idx + query.length);
      frag.appendChild(mark);
      frag.appendChild(document.createTextNode(texto.slice(idx + query.length)));
      nodo.replaceWith(frag);
    });
  });
}

/* ── Expandir / Colapsar todo ────────────────────────────── */

function expandirTodo(expandir) {
  const root = trazasBody.querySelector(".tsec-root");
  if (!root) return;
  root.querySelectorAll(".tsec-block").forEach(bloque => {
    const body = bloque.querySelector(":scope > .tsec-body");
    const btn  = bloque.querySelector(":scope > .tsec-header > .tsec-toggle");
    if (!body || !btn) return;
    body.style.display = expandir ? "" : "none";
    btn.textContent    = expandir ? "▾" : "▸";
  });
}

/* ── Copiar plano ─────────────────────────────────────────── */

async function copiarPlano() {
  const texto = window._trazasContenido || "";
  if (!texto) return;
  try {
    await navigator.clipboard.writeText(texto);
    const btn = document.getElementById("btnCopyPlano");
    btn.textContent = "✓ Copiado";
    btn.classList.add("copied");
    setTimeout(() => {
      btn.textContent = "📋 Copiar";
      btn.classList.remove("copied");
    }, 2000);
  } catch {
    // Fallback para navegadores sin permiso clipboard
    const ta = document.createElement("textarea");
    ta.value = texto;
    ta.style.position = "fixed";
    ta.style.opacity  = "0";
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
  }
}