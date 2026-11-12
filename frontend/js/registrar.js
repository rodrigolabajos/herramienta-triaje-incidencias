// registrar.js — alta individual e importación masiva CSV

const registrarBtn = document.getElementById("registrarBtn");
const mensajeBox   = document.getElementById("mensajeBox");
const csvFileInput = document.getElementById("csvFileInput");
const importResult = document.getElementById("importResult");

function mostrarMensaje(texto, tipo) {
  mensajeBox.className = "";
  const m = {exito:"msg-exito", error:"msg-error", validacion:"msg-validacion"};
  mensajeBox.classList.add(m[tipo] || "msg-error");
  mensajeBox.textContent = texto;
  mensajeBox.classList.remove("hidden");
}
function ocultarMensaje() { mensajeBox.classList.add("hidden"); mensajeBox.textContent = ""; }

registrarBtn.addEventListener("click", async () => {
  ocultarMensaje();
  const idIncidencia  = document.getElementById("idIncidencia").value.trim();
  const deptoOrigen   = document.getElementById("deptoOrigen").value;
  const errorVal      = document.getElementById("errorInput").value.trim();
  const descripcion   = document.getElementById("descripcionInput").value.trim();
  const deptoAsignado = document.getElementById("deptoAsignado").value;
  const trazasVal     = document.getElementById("trazasInput").value.trim();

  if (!/^(INC|WO)-[A-Z0-9]+$/.test(idIncidencia)) {
    mostrarMensaje("⚠ El ID debe empezar por INC- o WO- (ej: INC-0001, WO-12345).", "validacion"); return;
  }
  if (!deptoOrigen)                       { mostrarMensaje("⚠ Selecciona el Departamento Origen.", "validacion"); return; }
  if (!descripcion || descripcion.length < 10) { mostrarMensaje("⚠ La descripción debe tener al menos 10 caracteres.", "validacion"); return; }
  if (!deptoAsignado)                     { mostrarMensaje("⚠ Selecciona el Departamento Asignado.", "validacion"); return; }

  registrarBtn.disabled = true; registrarBtn.textContent = "Registrando…";
  try {
    const response = await fetch(`${API_BASE}/incidencias/`, {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        id_incidencia: idIncidencia, departamento_origen: deptoOrigen,
        descripcion, departamento_asignado: deptoAsignado,
        error: errorVal || null,
        trazas: trazasVal || null
      })
    });
    if (response.status === 409) { mostrarMensaje("⚠ Ya existe una incidencia con ese ID.", "validacion"); return; }
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      mostrarMensaje(`✗ Error del servidor: ${err?.detail?.[0]?.msg || err?.detail || "Error desconocido"}`, "error"); return;
    }
    const data = await response.json();
    mostrarMensaje(`✓ Incidencia ${data.id_incidencia} registrada correctamente.`, "exito");
    ["idIncidencia","deptoOrigen","errorInput","descripcionInput","deptoAsignado","trazasInput"].forEach(id => {
      document.getElementById(id).value = "";
    });
  } catch (err) {
    mostrarMensaje(`✗ No se pudo conectar con el servidor: ${err.message}`, "error");
  } finally {
    registrarBtn.disabled = false; registrarBtn.textContent = "Registrar Incidencia";
  }
});

// ── IMPORTACIÓN MASIVA CSV ────────────────────────────────────────────────────
csvFileInput.addEventListener("change", async () => {
  const file = csvFileInput.files[0];
  if (!file) return;
  importResult.className = "msg-validacion";
  importResult.textContent = "⏳ Procesando…";
  importResult.classList.remove("hidden");

  try {
    const text   = await file.text();
    const lines  = text.trim().split(/\r?\n/);
    const header = lines[0].split(",").map(h => h.trim().replace(/"/g,"").toLowerCase());
    const idx    = {
      id:     header.indexOf("id_incidencia"),
      origen: header.indexOf("departamento_origen"),
      desc:   header.indexOf("descripcion"),
      asig:   header.indexOf("departamento_asignado"),
      error:  header.indexOf("error"),
      trazas: header.indexOf("trazas")
    };
    if (idx.id < 0 || idx.origen < 0 || idx.desc < 0 || idx.asig < 0) {
      importResult.className = "msg-error";
      importResult.textContent = "✗ Cabeceras no encontradas. Revisa el formato del CSV.";
      csvFileInput.value = ""; return;
    }
    const filas = [];
    for (let i = 1; i < lines.length; i++) {
      const c = lines[i].split(",").map(x => x.trim().replace(/^"|"$/g,""));
      if (!c[idx.id]) continue;
      filas.push({
        id_incidencia: c[idx.id], departamento_origen: c[idx.origen],
        descripcion: c[idx.desc], departamento_asignado: c[idx.asig],
        error: idx.error >= 0 && c[idx.error] ? c[idx.error] : null,
        trazas: idx.trazas >= 0 && c[idx.trazas] ? c[idx.trazas] : null
      });
    }
    if (!filas.length) {
      importResult.className = "msg-validacion";
      importResult.textContent = "⚠ No se encontraron filas válidas.";
      csvFileInput.value = ""; return;
    }
    const res  = await fetch(`${API_BASE}/incidencias/import/csv`, {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify(filas)
    });
    const data = await res.json();
    importResult.className = data.insertadas > 0 ? "msg-exito" : "msg-validacion";
    importResult.textContent = `✓ ${data.insertadas} insertadas · ${data.duplicadas} duplicadas${data.errores.length ? ` · ${data.errores.length} errores` : ""}`;
  } catch (err) {
    importResult.className = "msg-error";
    importResult.textContent = `✗ Error: ${err.message}`;
  }
  csvFileInput.value = "";
});
