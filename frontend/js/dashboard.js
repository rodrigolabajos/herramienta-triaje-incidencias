// dashboard.js

async function cargar() {
  try {
    const data = await fetch(`${API_BASE}/incidencias/stats/dashboard`).then(r => r.json());

    document.getElementById("kpiTotal").textContent      = data.total;
    document.getElementById("dashTotalHdr").textContent  = `${data.total} incidencias`;
    document.getElementById("kpiFlujos").textContent     = data.flujos_reasignacion.length;
    document.getElementById("kpiRecientes").textContent  = data.evolucion.reduce((s,d)=>s+d.total,0);
    if (data.por_departamento[0])
      document.getElementById("kpiTopDepto").textContent = data.por_departamento[0].departamento;

    renderBarras("chartDeptos",  data.por_departamento,  "departamento", "total", "var(--accent)");
    renderFlujos("chartFlujos",  data.flujos_reasignacion);
    renderEvolucion("chartEvol", "evolLegend", data.evolucion);
    renderBarras("chartErrores", data.top_errores,       "error",        "total", "var(--amber)");
  } catch (e) {
    document.querySelector(".app-container").innerHTML += `<p style="color:var(--red);padding:20px">Error: ${e.message}</p>`;
  }
}

function renderBarras(id, items, labelKey, cntKey, color) {
  const el = document.getElementById(id);
  if (!items?.length) { el.innerHTML = `<p class="dash-empty">Sin datos</p>`; return; }
  const max = Math.max(...items.map(i => i[cntKey]));
  el.innerHTML = items.map(item => `
    <div class="bar-row">
      <span class="bar-label" title="${item[labelKey]}">${item[labelKey]}</span>
      <div class="bar-track"><div class="bar-fill" style="width:${max?((item[cntKey]/max)*100).toFixed(1):0}%;background:${color}"></div></div>
      <span class="bar-cnt">${item[cntKey]}</span>
    </div>`).join("");
}

function renderFlujos(id, flujos) {
  const el = document.getElementById(id);
  if (!flujos?.length) { el.innerHTML = `<p class="dash-empty">Sin reasignaciones</p>`; return; }
  el.innerHTML = flujos.map(f => `
    <div class="flujo-row">
      <span class="flujo-badge">${f.origen}</span>
      <span class="flujo-arrow">→</span>
      <span class="flujo-badge flujo-badge-dest">${f.asignado}</span>
      <span class="flujo-cnt">${f.total}×</span>
    </div>`).join("");
}

function renderEvolucion(id, legendId, evolucion) {
  const el = document.getElementById(id);
  const lg = document.getElementById(legendId);
  if (!evolucion?.length) { el.innerHTML = `<p class="dash-empty">Sin datos</p>`; return; }
  const max = Math.max(...evolucion.map(d => d.total));
  el.innerHTML = evolucion.map(d => {
    const h = max ? ((d.total/max)*100).toFixed(1) : 0;
    return `<div class="evol-bar" style="height:${h}%" title="${d.dia}: ${d.total}"></div>`;
  }).join("");
  if (evolucion.length > 1)
    lg.textContent = `${evolucion[0].dia} → ${evolucion[evolucion.length-1].dia}`;
}

cargar();
