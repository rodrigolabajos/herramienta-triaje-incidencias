"""
API de documentación relacionada.

Endpoints:
  GET  /documentacion/incidencia/{id_incidencia}  — documentos relacionados
  POST /documentacion/batch-check                 — check masivo para el historial (1 request = N incidencias)
  GET  /documentacion/ver/{id_documento}          — sirve el fichero original
  GET  /documentacion/texto/{id_documento}        — devuelve texto extraído
  POST /documentacion/indexar                     — lanza indexación manual
"""

import os
import logging
import asyncio
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

from backend.database.database import get_connection
from backend.services.documentacion_indexer import extraer_texto
from backend.utils import extraer_palabras, normalizar

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Resolver DOCUMENTACION_ROOT ────────────────────────────────
def _resolver_docs_root() -> Path:
    raw = os.getenv("DOCUMENTACION_ROOT", "./documentacion")
    p = Path(raw)
    if not p.is_absolute():
        p = (Path(__file__).resolve().parents[2] / p).resolve()
    return p

EXTENSIONES_PERMITIDAS = {".pdf", ".docx", ".odt", ".txt", ".sql"}
MIME_MAP = {
    ".pdf":  "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".odt":  "application/vnd.oasis.opendocument.text",
    ".txt":  "text/plain; charset=utf-8",
    ".sql":  "text/plain; charset=utf-8",
}


# ════════════════════════════════════════════════════════════════
# ÍNDICES AUXILIARES (una vez al arrancar)
# ════════════════════════════════════════════════════════════════

def _ensure_indexes():
    try:
        conn = get_connection()
        conn.executescript("""
            CREATE INDEX IF NOT EXISTS idx_doc_keywords ON documentos_indexados(keywords);
            CREATE INDEX IF NOT EXISTS idx_doc_nombre   ON documentos_indexados(nombre_archivo);
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Índices auxiliares: {e}")

_ensure_indexes()


# ════════════════════════════════════════════════════════════════
# CACHÉ DE DOCUMENTOS EN MEMORIA
# Se carga una sola vez por proceso y se invalida al indexar.
# Elimina el SELECT masivo repetido en cada request del historial.
# ════════════════════════════════════════════════════════════════

_docs_cache: list[dict] | None = None

def _get_docs_cache() -> list[dict]:
    global _docs_cache
    if _docs_cache is None:
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT id, nombre_archivo, extension, carpeta_relativa, keywords, estado "
                "FROM documentos_indexados WHERE estado != 'eliminado'"
            ).fetchall()
        finally:
            conn.close()
        cols = ["id", "nombre_archivo", "extension", "carpeta_relativa", "keywords", "estado"]
        _docs_cache = [dict(zip(cols, r)) for r in rows]
    return _docs_cache

def _invalidar_cache():
    global _docs_cache
    _docs_cache = None


# ════════════════════════════════════════════════════════════════
# SCORING LIGERO — keywords + nombre + carpeta, sin texto completo
# ════════════════════════════════════════════════════════════════

def _scoring_ligero(incidencia: dict, documentos: list[dict]) -> list[dict]:
    error          = normalizar(incidencia.get("error") or "")
    descripcion    = incidencia.get("descripcion") or ""
    depto          = normalizar(incidencia.get("depto_asignado") or "")
    palabras_desc  = [p for p in extraer_palabras(descripcion) if len(p) > 3]
    palabras_error = [p for p in extraer_palabras(error) if len(p) > 2]

    resultados = []
    for doc in documentos:
        if doc["estado"] in ("eliminado", "error"):
            continue

        nombre_n   = normalizar(doc["nombre_archivo"])
        carpeta_n  = normalizar(doc.get("carpeta_relativa") or "")
        keywords_n = normalizar(doc.get("keywords") or "")
        haystack_kw   = keywords_n
        haystack_ruta = nombre_n + " " + carpeta_n
        haystack_all  = haystack_ruta + " " + haystack_kw

        score = 0; motivos = []

        if error and len(error) > 2 and error in haystack_all:
            score += 40; motivos.append("error exacto")

        hits = [p for p in palabras_desc if p in haystack_kw]
        if hits:
            score += min(25, len(hits) * 6)
            motivos.append(f"desc→keywords ({len(hits)})")

        if depto and len(depto) > 2 and depto in haystack_all:
            score += 20; motivos.append("departamento")

        hits_e = [p for p in palabras_error if p in haystack_kw]
        if hits_e:
            score += min(15, len(hits_e) * 5)
            motivos.append(f"error→keywords ({len(hits_e)})")

        hits_r = [p for p in palabras_desc if p in haystack_ruta]
        if hits_r:
            score += min(10, len(hits_r) * 4)
            motivos.append(f"desc→nombre ({len(hits_r)})")

        if score == 0:
            continue

        resultados.append({
            "id":               doc["id"],
            "nombre_archivo":   doc["nombre_archivo"],
            "extension":        doc["extension"],
            "carpeta_relativa": doc.get("carpeta_relativa") or "",
            "score":            score,
            "motivo":           ", ".join(motivos),
            "preview":          "",
        })

    resultados.sort(key=lambda x: x["score"], reverse=True)
    return resultados[:10]


def _enriquecer_con_preview(resultados: list[dict]) -> list[dict]:
    if not resultados:
        return resultados
    ids = [r["id"] for r in resultados]
    ph  = ",".join("?" * len(ids))
    conn = get_connection()
    try:
        rows = conn.execute(
            f"SELECT id, SUBSTR(texto_extraido,1,301) FROM documentos_indexados WHERE id IN ({ph})",
            ids
        ).fetchall()
    finally:
        conn.close()
    pm = {row[0]: row[1] for row in rows}
    for r in resultados:
        raw = pm.get(r["id"]) or ""
        r["preview"] = raw[:300] + ("…" if len(raw) > 300 else "")
    return resultados


def _buscar_documentos(id_incidencia: str):
    """Ejecutar en thread. Devuelve (incidencia|None, docs_scored)."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id_incidencia, descripcion, depto_asignado, error "
            "FROM incidencias WHERE id_incidencia = ?", (id_incidencia,)
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return None, []

    incidencia = {"id_incidencia": row[0], "descripcion": row[1],
                  "depto_asignado": row[2], "error": row[3]}

    documentos = _get_docs_cache()
    if not documentos:
        return incidencia, []

    scored = _scoring_ligero(incidencia, documentos)
    scored = _enriquecer_con_preview(scored)
    return incidencia, scored


# ════════════════════════════════════════════════════════════════
# FUNCIÓN PÚBLICA para ia.py
# ════════════════════════════════════════════════════════════════

def buscar_docs_relevantes_para_ia(id_incidencia: str, max_chars: int = 1500) -> str:
    """
    Devuelve bloque de texto compacto con docs relevantes para el contexto IA.
    Usa la caché en memoria — no hace SELECT masivo.
    """
    _, docs = _buscar_documentos(id_incidencia)
    if not docs:
        return ""
    bloques = []; acum = 0
    for d in docs:
        if acum >= max_chars:
            break
        bloque = (
            f"[DOC: {d['nombre_archivo']} | score {d['score']}]\n"
            f"Carpeta: {d['carpeta_relativa']}\n"
            f"Motivo: {d['motivo']}\n"
            f"Extracto: {d['preview']}"
        )
        bloques.append(bloque)
        acum += len(bloque)
    return "\n\n".join(bloques)


# ════════════════════════════════════════════════════════════════
# ENDPOINTS
# ════════════════════════════════════════════════════════════════

@router.get("/incidencia/{id_incidencia}")
async def documentos_por_incidencia(id_incidencia: str):
    incidencia, docs = await asyncio.to_thread(_buscar_documentos, id_incidencia)
    if incidencia is None:
        return JSONResponse(status_code=404, content={"error": "Incidencia no encontrada"})
    if not docs:
        return JSONResponse({"id_incidencia": id_incidencia, "documentos": [],
                             "aviso": "No hay documentos relacionados."})
    return JSONResponse({"id_incidencia": id_incidencia, "documentos": docs})


@router.post("/batch-check")
async def batch_check(payload: dict):
    """
    Recibe {"ids": ["INC-001", "INC-002", ...]}
    Devuelve {"INC-001": true, "INC-002": false, ...}

    UNA sola petición desde el historial en vez de N paralelas.
    Usa la caché de documentos en memoria: O(N_incidencias × N_docs_en_memoria).
    """
    ids: list[str] = payload.get("ids", [])
    if not ids:
        return JSONResponse({})

    documentos = _get_docs_cache()
    resultado  = {id_: False for id_ in ids}

    if not documentos:
        return JSONResponse(resultado)

    def _check_batch_sync():
        conn = get_connection()
        try:
            ph   = ",".join("?" * len(ids))
            rows = conn.execute(
                f"SELECT id_incidencia, descripcion, depto_asignado, error "
                f"FROM incidencias WHERE id_incidencia IN ({ph})", ids
            ).fetchall()
        finally:
            conn.close()

        for row in rows:
            inc = {"id_incidencia": row[0], "descripcion": row[1],
                   "depto_asignado": row[2], "error": row[3]}
            scored = _scoring_ligero(inc, documentos)
            resultado[row[0]] = len(scored) > 0
        return resultado

    res = await asyncio.to_thread(_check_batch_sync)
    return JSONResponse(res)


@router.get("/ver/{id_documento}")
async def ver_documento(id_documento: int):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT ruta, nombre_archivo, extension, estado FROM documentos_indexados WHERE id = ?",
            (id_documento,)
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return JSONResponse(status_code=404, content={"error": "Documento no encontrado"})

    ruta_str, nombre, extension, estado = row
    if estado == "eliminado":
        return JSONResponse(status_code=410, content={"error": "Documento eliminado"})

    ruta = Path(ruta_str)
    docs_root = _resolver_docs_root()
    try:
        ruta.resolve().relative_to(docs_root.resolve())
    except ValueError:
        logger.warning(f"Acceso fuera de DOCUMENTACION_ROOT: {ruta_str}")
        return JSONResponse(status_code=403, content={"error": "Acceso denegado"})

    if not ruta.exists():
        return JSONResponse(status_code=404, content={"error": "Fichero no encontrado en disco"})
    if extension not in EXTENSIONES_PERMITIDAS:
        return JSONResponse(status_code=400, content={"error": "Extensión no permitida"})

    return FileResponse(str(ruta), media_type=MIME_MAP.get(extension, "application/octet-stream"),
                        filename=nombre)


@router.get("/texto/{id_documento}")
async def texto_documento(id_documento: int):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, nombre_archivo, extension, texto_extraido, estado, ruta "
            "FROM documentos_indexados WHERE id = ?", (id_documento,)
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return JSONResponse(status_code=404, content={"error": "Documento no encontrado"})

    _id, nombre, extension, texto, estado, ruta_str = row
    if estado == "eliminado":
        return JSONResponse(status_code=410, content={"error": "Documento eliminado"})
    if extension not in EXTENSIONES_PERMITIDAS:
        return JSONResponse(status_code=400, content={"error": "Extensión no permitida"})

    if extension != ".pdf":
        ruta = Path(ruta_str)
        docs_root = _resolver_docs_root()
        try:
            ruta.resolve().relative_to(docs_root.resolve())
        except ValueError:
            return JSONResponse(status_code=403, content={"error": "Acceso denegado"})
        if ruta.exists():
            try:
                texto = extraer_texto(ruta)
            except RuntimeError:
                pass

    return JSONResponse({"id": _id, "nombre": nombre, "extension": extension, "texto": texto or ""})


@router.post("/indexar")
async def indexar_manual():
    from backend.services.documentacion_indexer import indexar
    docs_root = _resolver_docs_root()
    stats = await asyncio.to_thread(indexar, docs_root)
    _invalidar_cache()  # Forzar recarga del caché tras indexar
    return JSONResponse({"docs_root": str(docs_root), "stats": stats})
