// consulta.js — búsqueda, triaje, chat IA

function mensajeEstado(c) {
  if (c >= 0.6)  return 'Alta confianza en casos históricos similares.';
  if (c >= 0.35) return 'Confianza moderada. Se recomienda revisión.';
  return 'Confianza baja. Revisión manual recomendada.';
}

function showToast(text) {
  const t = document.getElementById('toast');
  t.textContent = text;
  t.classList.remove('hidden');
  t.classList.add('show');
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.remove('show'), 2500);
}

// ─── REFS ────────────────────────────────────────────────
const buscarBtn          = document.getElementById('buscarBtn');
const descripcionInput   = document.getElementById('descripcionInput');
const errorInput         = document.getElementById('errorInput');
const departamentoSelect = document.getElementById('departamentoSelect');
const resultadoBox       = document.getElementById('resultadoBox');
const deptoResultado     = document.getElementById('departamentoResultado');
const confianzaResultado = document.getElementById('confianzaResultado');
const confidenceFill     = document.getElementById('confidenceFill');
const iaCard             = document.getElementById('iaCard');
const iaExplanation      = document.getElementById('iaExplanation');
const iaQuestionBox      = document.getElementById('iaQuestionBox');
const iaQuestionInput    = document.getElementById('iaQuestionInput');
const iaAskBtn           = document.getElementById('iaAskBtn');
const listaResultados    = document.getElementById('listaResultados');
const triajeConfirm      = document.getElementById('triaje-confirm');
const btnOk              = document.getElementById('btnTriajeOk');
const btnKo              = document.getElementById('btnTriajeKo');
const triajeFeedback     = document.getElementById('triajeFeedback');
const correccionBox      = document.getElementById('correccionBox');
const deptoCorreccion    = document.getElementById('deptoCorreccion');
const btnEnviarCorrec    = document.getElementById('btnEnviarCorreccion');
const btnIaExpand        = document.getElementById('btnIaExpand');
const iaOverlay          = document.getElementById('iaOverlay');
const btnModalClose      = document.getElementById('btnModalClose');
const chatMessages       = document.getElementById('chatMessages');
const modalInput         = document.getElementById('modalInput');
const modalSendBtn       = document.getElementById('modalSendBtn');
const limpiarBtn         = document.getElementById('limpiarBtn');
// Nota: trazasOverlay, trazasBody, etc. los gestiona trazas.js

// ─── STATE ───────────────────────────────────────────────
let iaInputAbierto  = false;
let lastSearchParams = {};
let historial        = [];
let deptoRecomendado = null;
let descripcionActual = '';
let lastInputState   = '';
let contextoIdActual = null;

// ─── DIRTY CHECK ─────────────────────────────────────────
function getInputState() {
  return JSON.stringify({
    d: descripcionInput.value.trim(),
    e: errorInput.value.trim(),
    dep: departamentoSelect.value
  });
}

function checkSearchDirty() {
  const was = buscarBtn.disabled;
  buscarBtn.disabled = (getInputState() === lastInputState);
  if (was && !buscarBtn.disabled) {
    buscarBtn.classList.add('ready');
    setTimeout(() => buscarBtn.classList.remove('ready'), 300);
  }
}

[descripcionInput, errorInput, departamentoSelect].forEach(el =>
  el.addEventListener('input', checkSearchDirty)
);

// ─── BUSCAR ──────────────────────────────────────────────
async function ejecutarBusqueda() {
  const descripcion = descripcionInput.value.trim();
  const error       = errorInput.value.trim();
  const departamento = departamentoSelect.value.trim();

  if (descripcion.length < 3) { showToast('Introduce una descripción con al menos 3 caracteres'); return; }

  lastInputState = getInputState();
  checkSearchDirty();
  lastSearchParams = { descripcion, error: error || null, departamento: departamento || null };
  historial = [];
  deptoRecomendado = null;
  descripcionActual = descripcion;

  buscarBtn.disabled = true;
  buscarBtn.innerHTML = "🔍 Buscando<span class='dots'>...</span>";
  listaResultados.style.opacity = '.5';
  listaResultados.innerHTML = `
    <div class="empty-state"><div class="empty-icon">⏳</div><div>Buscando incidencias similares…</div></div>
    <div style="margin-top:14px">
      <div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div>
    </div>`;

  resultadoBox.style.display = 'none';
  iaCard.style.display = 'none';
  correccionBox.classList.add('hidden');
  triajeFeedback.textContent = '';
  btnOk.disabled = btnKo.disabled = false;

  try {
    const params = [`descripcion=${encodeURIComponent(descripcion)}`];

    if (error) {
      params.push(`error=${encodeURIComponent(error)}`);
    }

    if (departamento) {
      params.push(`departamento=${encodeURIComponent(departamento)}`);
    }

    const r = await fetch(`${API_BASE}/buscar?${params.join('&')}`);

    if (!r.ok) throw new Error(`Error ${r.status}`);
    const data = await r.json();

    contextoIdActual = data.contexto_id || null;

    listaResultados.innerHTML = '';

    if (!data.resultados || !data.resultados.length) {
      listaResultados.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">🚫</div>
          <div>No se encontraron incidencias similares.<br>
            <span style="font-size:12px;opacity:.7">Prueba con una descripción más general o sin código de error.</span>
          </div>
        </div>`;
      return;
    }

    deptoRecomendado = data.departamento_recomendado;
    deptoResultado.textContent = data.departamento_recomendado;
    const pct = (data.confianza * 100).toFixed(0);
    confianzaResultado.textContent = `Confianza: ${pct}% — ${mensajeEstado(data.confianza)}`;
    confidenceFill.style.width = '0%';
    requestAnimationFrame(() => confidenceFill.style.width = pct + '%');
    resultadoBox.style.display = 'block';
    resultadoBox.classList.add('show');

    iaExplanation.textContent = data.explicacion_ia;
    iaCard.style.display = 'block';
    iaCard.classList.add('new');
    setTimeout(() => iaCard.classList.remove('new'), 600);

    chatMessages.innerHTML = '';
    addBubble('system', `Incidencia: "${descripcion}" → ${deptoRecomendado}`);
    addBubble('assistant', data.explicacion_ia);

    // Header resultados
    const hdr = document.createElement('div');
    hdr.className = 'results-header';
    hdr.innerHTML = `<span>Resultados similares</span><span class="results-count-badge">${data.resultados.length} encontradas</span>`;
    listaResultados.appendChild(hdr);

    // Filtro score
    const filterBar = document.createElement('div');
    filterBar.className = 'score-filter-bar';
    filterBar.innerHTML = `
      <button class="score-filter-btn active" data-min="0">Todos</button>
      <button class="score-filter-btn" data-min="0.5">Alta similitud (≥50%)</button>
      <button class="score-filter-btn" data-min="0.25">Media+ (≥25%)</button>`;
    listaResultados.appendChild(filterBar);
    filterBar.querySelectorAll('.score-filter-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        filterBar.querySelectorAll('.score-filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const min = parseFloat(btn.dataset.min);
        listaResultados.querySelectorAll('.result-card').forEach(c => {
          c.style.display = parseFloat(c.dataset.score || 1) >= min ? '' : 'none';
        });
      });
    });

    // Tarjetas
    data.resultados.forEach((r, i) => {
      const card = document.createElement('div');
      card.className = 'result-card';
      card.style.animationDelay = `${i * 0.05}s`;
      card.dataset.score = r.score;

      const fechaStr = r.fecha_registro
        ? new Date(r.fecha_registro).toLocaleDateString('es-ES', { day: '2-digit', month: 'short', year: 'numeric' })
        : '';

      card.innerHTML = `
        <div class="result-card-header">
          <span class="result-id">${r.id_incidencia}</span>
          <span class="score-badge ${r.score >= 0.5 ? 'score-high' : r.score >= 0.25 ? 'score-mid' : 'score-low'}">
            ${(r.score * 100).toFixed(0)}%
          </span>
          <span class="expand-hint">+ info</span>
        </div>
        <p class="result-desc">${resaltarTexto(r.descripcion, descripcion)}</p>
        <span class="result-depto">${r.departamento_asignado}</span>
        <div class="result-card-extra">
          <div class="card-meta-row">
            <div class="card-meta-left">
              ${fechaStr ? `<span class="card-fecha">📅 ${fechaStr}</span>` : ''}
              ${r.error ? `<span class="card-fecha">🔴 ${r.error}</span>` : ''}
            </div>
            <div class="card-meta-actions">
              ${r.tiene_trazas
                ? `<button class="btn-ver-trazas" data-id="${r.id_incidencia}">📋 Ver trazas</button>`
                : `<span class="card-fecha" style="opacity:.4">Sin trazas</span>`
              }
              <button class="btn-ver-docs btn-docs-consulta" data-id="${r.id_incidencia}" style="display:none">📚 Documentación</button>
            </div>
          </div>
        </div>`;

      card.addEventListener('click', e => {
        if (e.target.closest('.btn-ver-trazas') || e.target.closest('.result-id')) return;
        card.classList.toggle('expanded');
      });

      card.querySelector('.result-id').addEventListener('click', e => {
        e.stopPropagation();
        navigator.clipboard.writeText(r.id_incidencia).then(() => showToast(`📋 ${r.id_incidencia} copiado`));
      });

      const btnTrazas = card.querySelector('.btn-ver-trazas');
      if (btnTrazas) {
        btnTrazas.addEventListener('click', e => { e.stopPropagation(); abrirTrazas(r.id_incidencia); });
      }

      const btnDocs = card.querySelector('.btn-ver-docs');
      if (btnDocs) {
        btnDocs.addEventListener('click', e => { e.stopPropagation(); abrirDocumentacion(r.id_incidencia); });
      }

      listaResultados.appendChild(card);
    });

    mostrarBotonesDocumentacion(data.resultados.map(r => r.id_incidencia));

    requestAnimationFrame(() => { listaResultados.style.opacity = '1'; });

  } catch (err) {
    listaResultados.innerHTML = `<div class="empty-state"><div class="empty-icon">⚠️</div><div>Error: ${err.message}</div></div>`;
  } finally {
    buscarBtn.textContent = '🔍 Buscar';
    checkSearchDirty();
  }
}

async function mostrarBotonesDocumentacion(ids) {
  if (!ids.length) return;

  try {
    const checks = await Promise.allSettled(
      ids.map(id =>
        fetch(`${API_BASE}/documentacion/incidencia/${encodeURIComponent(id)}`)
          .then(r => r.ok ? r.json() : null)
      )
    );

    checks.forEach((result, i) => {
      const tieneDocs = result.status === 'fulfilled'
        && result.value
        && result.value.documentos
        && result.value.documentos.length > 0;

      if (!tieneDocs) return;

      const btn = listaResultados.querySelector(`.btn-docs-consulta[data-id="${ids[i]}"]`);
      if (btn) btn.style.display = '';
    });
  } catch { /* si falla el check, los botones permanecen ocultos */ }
}

buscarBtn.addEventListener('click', ejecutarBusqueda);
descripcionInput.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); ejecutarBusqueda(); } });

// ─── TRIAJE ──────────────────────────────────────────────
btnOk.addEventListener('click', () => { btnOk.disabled = btnKo.disabled = true; triajeFeedback.textContent = '✓ ¡Gracias!'; });
btnKo.addEventListener('click', () => correccionBox.classList.toggle('hidden'));

btnEnviarCorrec.addEventListener('click', async () => {
  if (!deptoCorreccion.value) { showToast('Selecciona el departamento correcto'); return; }
  btnEnviarCorrec.disabled = true;
  btnEnviarCorrec.textContent = 'Registrando…';
  try {
    await fetch(`${API_BASE}/incidencias/`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        id_incidencia: 'INC-' + Date.now().toString().slice(-7),
        departamento_origen: deptoRecomendado || 'CAU',
        descripcion: descripcionActual,
        departamento_asignado: deptoCorreccion.value,
        error: lastSearchParams.error || null
      })
    });
    triajeConfirm.style.opacity = '.6';
    triajeFeedback.textContent = '✓ Corrección registrada';
    showToast('Corrección guardada');
  } finally {
    btnEnviarCorrec.disabled = false;
    btnEnviarCorrec.textContent = 'Confirmar corrección';
  }
});

// ─── HELPERS ─────────────────────────────────────────────
function addBubble(role, texto) {
  const div = document.createElement('div');
  div.className = `chat-bubble ${role}`;
  div.textContent = texto;
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return div;
}

function resaltarTexto(texto, query) {
  if (!query) return texto;
  return texto.replace(new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi'), '<mark>$1</mark>');
}

function scrollChat() { chatMessages.scrollTop = chatMessages.scrollHeight; }

// ─── IA CARD inline ──────────────────────────────────────
iaCard.addEventListener('click', e => {
  e.stopPropagation();
  iaInputAbierto = !iaInputAbierto;
  iaQuestionBox.classList.toggle('hidden', !iaInputAbierto);
  if (iaInputAbierto) iaQuestionInput.focus();
});
iaQuestionBox.addEventListener('click', e => e.stopPropagation());
document.addEventListener('click', () => {
  if (!iaInputAbierto) return;
  iaQuestionBox.classList.add('hidden');
  iaInputAbierto = false;
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && iaInputAbierto) { iaQuestionBox.classList.add('hidden'); iaInputAbierto = false; }
});

iaAskBtn.addEventListener('click', () => enviarPregunta(iaQuestionInput.value.trim(), false));
iaQuestionInput.addEventListener('keydown', e => { if (e.key === 'Enter') iaAskBtn.click(); });

// ─── MODAL IA ────────────────────────────────────────────
btnIaExpand.addEventListener('click', e => { e.stopPropagation(); iaOverlay.classList.remove('hidden'); modalInput.focus(); scrollChat(); });
btnModalClose.addEventListener('click', () => iaOverlay.classList.add('hidden'));
iaOverlay.addEventListener('click', e => { if (e.target === iaOverlay) iaOverlay.classList.add('hidden'); });
modalSendBtn.addEventListener('click', () => enviarPregunta(modalInput.value.trim(), true));
modalInput.addEventListener('keydown', e => { if (e.key === 'Enter') modalSendBtn.click(); });

// ─── ENVÍO PREGUNTAS ─────────────────────────────────────
async function enviarPregunta(pregunta, esModal) {
  if (!pregunta) return;
  const inputEl = esModal ? modalInput : iaQuestionInput;
  const btnEl   = esModal ? modalSendBtn : iaAskBtn;
  inputEl.value = '';
  btnEl.disabled = true;
  btnEl.textContent = '…';
  addBubble('user', pregunta);
  const typing = addBubble('assistant', '…');
  typing.classList.add('chat-typing');
  try {
  
    if (!contextoIdActual) {
      throw new Error('No hay contexto IA activo. Realiza una búsqueda primero.');
    }

    const r = await fetch(`${API_BASE}/buscar/chat-contextual`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        contexto_id: contextoIdActual,
        pregunta,
        historial: historial.slice(-4)
      })
    });

    if (!r.ok) throw new Error(`Error ${r.status}`);
    const data = await r.json();
    
    if (data.respuesta_ia) {
      typing.textContent = data.respuesta_ia;
      typing.classList.remove('chat-typing');
      iaExplanation.textContent = data.respuesta_ia;
      historial.push({ role: 'user', content: pregunta });
      historial.push({ role: 'assistant', content: data.respuesta_ia });
    }
  } catch (err) {
    typing.textContent = `Error: ${err.message}`;
    typing.classList.remove('chat-typing');
  } finally {
    btnEl.disabled = false;
    btnEl.textContent = 'Enviar';
    scrollChat();
    if (!esModal) { iaQuestionBox.classList.add('hidden'); iaInputAbierto = false; }
  }
}

// ─── LIMPIAR ─────────────────────────────────────────────
descripcionInput.addEventListener('input', () => limpiarBtn.classList.toggle('hidden', !descripcionInput.value));

limpiarBtn.addEventListener('click', () => {
  descripcionInput.value = '';
  errorInput.value = '';
  departamentoSelect.value = '';
  limpiarBtn.classList.add('hidden');
  resultadoBox.style.display = 'none';
  iaCard.style.display = 'none';
  listaResultados.innerHTML = `
    <div class="empty-state">
      <div class="empty-icon">🔎</div>
      <div>Introduce una descripción y pulsa Buscar<br>para ver incidencias similares</div>
    </div>`;
  lastInputState = '';
  checkSearchDirty();
  descripcionInput.focus();
});
