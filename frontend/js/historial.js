// historial.js — listado paginado con filtros

const tableBody   = document.getElementById("tableBody");
const searchInput = document.getElementById("searchInput");
const filterDepto = document.getElementById("filterDepto");
const btnPrev     = document.getElementById("btnPrev");
const btnNext     = document.getElementById("btnNext");
const paginInfo   = document.getElementById("paginInfo");
const hdrTotal    = document.getElementById("hdrTotal");
const btnExport   = document.getElementById("btnExportCSV");

const LIMIT = 20;
let offset = 0, total = 0, timer = null;

async function cargar() {
  const buscar = searchInput.value.trim();
  const depto  = filterDepto.value;
  const qs = [`limit=${LIMIT}`, `offset=${offset}`];
  if (buscar) qs.push(`buscar=${encodeURIComponent(buscar)}`);
  if (depto)  qs.push(`departamento=${encodeURIComponent(depto)}`);

  tableBody.innerHTML = `<tr><td colspan="8" class="tbl-empty">Cargando…</td></tr>`;
  try {
    const res  = await fetch(`${API_BASE}/incidencias/?${qs.join("&")}`);
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Error del servidor (${res.status})`);
    }
    const data = await res.json();
    total = data.total;
    hdrTotal.textContent = `${total} registros`;
    paginInfo.textContent = total
      ? `${offset + 1}–${Math.min(offset + LIMIT, total)} de ${total}`
      : "Sin resultados";
    btnPrev.disabled = offset === 0;
    btnNext.disabled = offset + LIMIT >= total;

    if (!data.incidencias.length) {
      tableBody.innerHTML = `<tr><td colspan="8" class="tbl-empty">No se encontraron incidencias</td></tr>`;
      return;
    }

    // Renderizar filas. El botón Docs comienza oculto; se muestra tras batch-check.
    tableBody.innerHTML = data.incidencias.map(inc => `
      <tr>
        <td class="td-mono td-bold">${inc.id_incidencia}</td>
        <td class="td-desc" title="${_escHtml(inc.descripcion)}">${_escHtml(inc.descripcion)}</td>
        <td><span class="badge-depto badge-asig">${inc.depto_asignado}</span></td>
        <td class="td-mono td-muted">${inc.error || "—"}</td>
        <td class="td-mono td-muted">${inc.fecha_registro ? inc.fecha_registro.slice(0,10) : "—"}</td>
        <td class="td-action">
          ${inc.tiene_trazas
            ? `<button class="btn-ver-trazas btn-trazas-hist" data-id="${inc.id_incidencia}">Trazas</button>`
            : `<span class="tbl-dash">—</span>`
          }
        </td>
        <td class="td-action td-docs">
          <button class="btn-ver-docs btn-docs-hist" data-id="${inc.id_incidencia}" style="display:none">Docs</button>
          <span class="tbl-dash tbl-docs-empty">—</span>
        </td>
        <td><button class="btn-delete" data-id="${inc.id_incidencia}">Eliminar</button></td>
      </tr>`).join("");

    tableBody.querySelectorAll(".btn-trazas-hist").forEach(btn =>
      btn.addEventListener("click", () => abrirTrazas(btn.dataset.id))
    );
    tableBody.querySelectorAll(".btn-docs-hist").forEach(btn =>
      btn.addEventListener("click", () => abrirDocumentacion(btn.dataset.id))
    );
    tableBody.querySelectorAll(".btn-delete").forEach(btn => {
      btn.addEventListener("click", async () => {
        if (!confirm(`¿Eliminar ${btn.dataset.id}?`)) return;
        btn.disabled = true; btn.textContent = "…";
        try {
          const r = await fetch(`${API_BASE}/incidencias/${encodeURIComponent(btn.dataset.id)}`, {method:"DELETE"});
          if (r.ok) { if (offset > 0 && offset >= total - 1) offset -= LIMIT; cargar(); }
          else { btn.disabled = false; btn.textContent = "Eliminar"; }
        } catch { btn.disabled = false; btn.textContent = "Eliminar"; }
      });
    });

    // Una sola petición POST al backend con los 20 IDs.
    // El backend hace scoring en memoria y devuelve {id: bool} instantáneamente.
    _checkDocsBatch(data.incidencias.map(i => i.id_incidencia));

  } catch (err) {
    tableBody.innerHTML = `<tr><td colspan="8" class="tbl-empty">Error: ${err.message}</td></tr>`;
  }
}

async function _checkDocsBatch(ids) {
  if (!ids.length) return;
  try {
    const res = await fetch(`${API_BASE}/documentacion/batch-check`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids }),
    });
    if (!res.ok) return;
    const mapa = await res.json(); // { "INC-001": true, "INC-002": false, ... }

    Object.entries(mapa).forEach(([id, tieneDoc]) => {
      if (!tieneDoc) return;
      const btn = tableBody.querySelector(`.btn-docs-hist[data-id="${id}"]`);
      if (!btn) return;
      btn.style.display = "";
      const empty = btn.parentElement.querySelector(".tbl-docs-empty");
      if (empty) empty.style.display = "none";
    });
  } catch { /* si falla el check, los botones permanecen ocultos */ }
}

function _escHtml(str) {
  return String(str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

btnPrev.addEventListener("click", () => { if (offset > 0) { offset -= LIMIT; cargar(); }});
btnNext.addEventListener("click", () => { if (offset + LIMIT < total) { offset += LIMIT; cargar(); }});
searchInput.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(() => { offset=0; cargar(); }, 350); });
filterDepto.addEventListener("change", () => { offset=0; cargar(); });
btnExport.addEventListener("click", e => { e.preventDefault(); window.location.href = `${API_BASE}/incidencias/export/csv`; });

cargar();
