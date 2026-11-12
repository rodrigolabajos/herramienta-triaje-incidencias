// documentacion.js — Modal de documentación relacionada por incidencia
// v2: skeleton instantáneo para que los botones sean visibles desde el primer momento

/* ── Abrir modal ─────────────────────────────────────────── */

async function abrirDocumentacion(idIncidencia) {
  const overlay = document.getElementById("docOverlay");
  const body    = document.getElementById("docBody");
  const titulo  = document.getElementById("docModalId");

  titulo.textContent = idIncidencia;

  // Mostrar skeleton de carga inmediatamente — el modal aparece sin esperar la API
  body.innerHTML = _renderSkeleton();
  overlay.classList.remove("hidden");

  try {
    const r = await fetch(`${API_BASE}/documentacion/incidencia/${encodeURIComponent(idIncidencia)}`);
    if (!r.ok) throw new Error(`Error ${r.status}`);
    const data = await r.json();

    if (data.aviso || !data.documentos || data.documentos.length === 0) {
      body.innerHTML = `
        <div class="doc-estado doc-vacio">
          <span class="doc-vacio-icon">📭</span>
          <p>No se encontró documentación relacionada</p>
          ${data.aviso ? `<small>${_esc(data.aviso)}</small>` : ""}
        </div>`;
      return;
    }

    _renderLista(data.documentos);
  } catch (e) {
    body.innerHTML = `<div class="doc-estado doc-vacio">⚠️ Error al cargar documentación: ${_esc(e.message)}</div>`;
  }
}

/* ── Skeleton de carga ───────────────────────────────────── */

function _renderSkeleton() {
  // Genera 3 tarjetas placeholder animadas. Los botones ya son visibles
  // (aunque desactivados) para que el usuario sepa que hay acciones disponibles.
  const tarjeta = `
    <div class="doc-item doc-item-skeleton">
      <div class="doc-item-main">
        <span class="doc-ext-badge skeleton-badge">···</span>
        <div class="doc-item-info">
          <span class="skeleton-line skeleton-line-largo"></span>
          <span class="skeleton-line skeleton-line-corto"></span>
          <span class="skeleton-line skeleton-line-medio"></span>
        </div>
        <span class="doc-score skeleton-score"></span>
      </div>
      <div class="doc-item-acciones">
        <button class="doc-btn-ver" disabled>👁️ Ver</button>
        <a class="doc-btn-descargar doc-btn-descargar-disabled">🡇 Descargar</a>
      </div>
    </div>`;

  return `
    <div class="doc-lista-header">
      <span class="skeleton-line skeleton-line-corto"></span>
    </div>
    <div class="doc-lista">
      ${tarjeta}${tarjeta}${tarjeta}
    </div>`;
}

/* ── Render lista de documentos ──────────────────────────── */

function _renderLista(documentos) {
  const body = document.getElementById("docBody");
  body.innerHTML = `
    <div class="doc-lista-header">
      <span>${documentos.length} documento${documentos.length !== 1 ? "s" : ""} relacionado${documentos.length !== 1 ? "s" : ""}</span>
    </div>
    <div class="doc-lista" id="docLista"></div>
    <div class="doc-visor hidden" id="docVisor">
      <div class="doc-visor-header">
        <button class="doc-visor-back" id="docVisorBack">← Volver a la lista</button>
        <span class="doc-visor-nombre" id="docVisorNombre"></span>
        <a class="doc-visor-descargar" id="docVisorDescargar" href="#" download>🡇 Descargar</a>
      </div>
      <div class="doc-visor-contenido" id="docVisorContenido"></div>
    </div>`;

  const lista = document.getElementById("docLista");

  documentos.forEach(doc => {
    const item = document.createElement("div");
    item.className = "doc-item";

    const scoreClass = doc.score >= 50 ? "doc-score-alto"
                     : doc.score >= 25 ? "doc-score-medio"
                     : "doc-score-bajo";

    item.innerHTML = `
      <div class="doc-item-main">
        <span class="doc-ext-badge">${_extLabel(doc.extension)}</span>
        <div class="doc-item-info">
          <span class="doc-item-nombre">${_esc(doc.nombre_archivo)}</span>
          <span class="doc-item-ruta">${_esc(doc.carpeta_relativa)}</span>
          <span class="doc-item-motivo">${_esc(doc.motivo)}</span>
        </div>
        <span class="doc-score ${scoreClass}">${doc.score}</span>
      </div>
      ${doc.preview ? `<div class="doc-item-preview">${_esc(doc.preview)}</div>` : ""}
      <div class="doc-item-acciones">
        <button class="doc-btn-ver" data-id="${doc.id}" data-ext="${doc.extension}" data-nombre="${_esc(doc.nombre_archivo)}">
          ${doc.extension === ".pdf" ? "👁️ Ver PDF" : "📄 Ver texto"}
        </button>
        <a class="doc-btn-descargar" href="${API_BASE}/documentacion/ver/${doc.id}" download="${_esc(doc.nombre_archivo)}">
          🡇 Descargar
        </a>
      </div>`;

    item.querySelector(".doc-btn-ver").addEventListener("click", () =>
      _abrirVisor(doc.id, doc.extension, doc.nombre_archivo)
    );

    lista.appendChild(item);
  });
}

/* ── Visor de documento ──────────────────────────────────── */

async function _abrirVisor(idDoc, extension, nombre) {
  const lista  = document.getElementById("docLista");
  const header = document.querySelector(".doc-lista-header");
  const visor  = document.getElementById("docVisor");
  const contenido = document.getElementById("docVisorContenido");
  const nombreEl  = document.getElementById("docVisorNombre");
  const descEl    = document.getElementById("docVisorDescargar");

  lista.classList.add("hidden");
  if (header) header.classList.add("hidden");
  visor.classList.remove("hidden");
  nombreEl.textContent = nombre;
  descEl.href     = `${API_BASE}/documentacion/ver/${idDoc}`;
  descEl.download = nombre;
  contenido.innerHTML = `<div class="doc-estado">Cargando…</div>`;

  document.getElementById("docVisorBack").onclick = () => {
    visor.classList.add("hidden");
    lista.classList.remove("hidden");
    if (header) header.classList.remove("hidden");
  };

  if (extension === ".pdf") {
    contenido.innerHTML = `
      <iframe
        src="${API_BASE}/documentacion/ver/${idDoc}"
        class="doc-iframe"
        title="Visor PDF"
      ></iframe>`;
  } else {
    try {
      const r = await fetch(`${API_BASE}/documentacion/texto/${idDoc}`);
      if (!r.ok) throw new Error(`Error ${r.status}`);
      const data = await r.json();
      const texto = data.texto || "(Sin texto extraído)";
      contenido.innerHTML = `<pre class="doc-texto-pre">${_esc(texto)}</pre>`;
    } catch (e) {
      contenido.innerHTML = `<div class="doc-estado doc-vacio">⚠️ No se pudo cargar el texto: ${_esc(e.message)}</div>`;
    }
  }
}

/* ── Cerrar modal ────────────────────────────────────────── */

document.getElementById("btnDocClose").addEventListener("click", _cerrarDoc);
document.getElementById("docOverlay").addEventListener("click", e => {
  if (e.target === document.getElementById("docOverlay")) _cerrarDoc();
});
document.addEventListener("keydown", e => {
  if (e.key !== "Escape") return;
  const trazasAbierto = document.getElementById("trazasOverlay") &&
    !document.getElementById("trazasOverlay").classList.contains("hidden");
  const iaAbierto = document.getElementById("iaOverlay") &&
    !document.getElementById("iaOverlay").classList.contains("hidden");
  if (trazasAbierto || iaAbierto) return;
  _cerrarDoc();
});

function _cerrarDoc() {
  document.getElementById("docOverlay").classList.add("hidden");
  document.getElementById("docBody").innerHTML = "";
}

/* ── Utilidades ──────────────────────────────────────────── */

function _esc(str) {
  return String(str || "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function _extLabel(ext) {
  const m = { ".pdf": "PDF", ".docx": "DOCX", ".odt": "ODT", ".txt": "TXT", ".sql": "SQL" };
  return m[ext] || ext.replace(".", "").toUpperCase();
}