"""
Indexador incremental de documentos de soporte.

Recorre DOCUMENTACION_ROOT, detecta ficheros nuevos o modificados,
extrae texto y actualiza la tabla documentos_indexados en SQLite.
NO reprocesa documentos sin cambios (compara size+mtime).

Uso:
    python -m backend.scripts.indexar_documentacion
    python -m backend.scripts.indexar_documentacion --limite 50
    python -m backend.scripts.indexar_documentacion --dry-run
"""

import hashlib
import logging
import os
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime

from backend.database.database import get_connection

logger = logging.getLogger(__name__)

EXTENSIONES_SOPORTADAS = {".pdf", ".docx", ".odt", ".txt", ".sql"}


# ════════════════════════════════════════════════════════════════
# EXTRACCIÓN DE TEXTO POR FORMATO
# ════════════════════════════════════════════════════════════════

def _extraer_pdf(path: Path) -> str:
    """Extrae texto de PDF con pypdf."""
    try:
        from pypdf import PdfReader
    except ImportError:
        logger.warning("PDF: instala 'pypdf' para extraer texto de PDFs.")
        return ""

    try:
        reader = PdfReader(str(path))
        partes = []
        for page in reader.pages:
            try:
                partes.append(page.extract_text() or "")
            except Exception:
                pass
        return "\n".join(partes).strip()
    except Exception as e:
        raise RuntimeError(f"PDF corrupto o no legible: {e}") from e


def _extraer_docx(path: Path) -> str:
    """Extrae texto de DOCX con python-docx."""
    try:
        from docx import Document
    except ImportError:
        logger.warning("DOCX: instala 'python-docx' para extraer texto de DOCX.")
        return ""
    try:
        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception as e:
        raise RuntimeError(f"DOCX no legible: {e}") from e


def _extraer_odt(path: Path) -> str:
    """Extrae texto de ODT leyendo content.xml y conservando párrafos."""
    try:
        with zipfile.ZipFile(str(path), "r") as z:
            if "content.xml" not in z.namelist():
                return ""
            xml_bytes = z.read("content.xml")

        root = ET.fromstring(xml_bytes)
        text_ns = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
        parrafos = []

        def texto_elemento(elem) -> str:
            partes = [elem.text or ""]
            for child in elem:
                if child.tag == f"{text_ns}line-break":
                    partes.append("\n")
                elif child.tag == f"{text_ns}tab":
                    partes.append("\t")
                else:
                    partes.append(texto_elemento(child))
                partes.append(child.tail or "")
            return "".join(partes)

        for elem in root.iter():
            if elem.tag in {f"{text_ns}p", f"{text_ns}h"}:
                texto = texto_elemento(elem).strip()
                if texto:
                    parrafos.append(texto)

        return "\n".join(parrafos).strip()
    except Exception as e:
        raise RuntimeError(f"ODT no legible: {e}") from e


def _extraer_txt(path: Path) -> str:
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    raise RuntimeError("TXT/SQL: no se pudo decodificar el fichero.")


def extraer_texto(path: Path) -> str:
    """Dispatcher por extensión. Devuelve texto plano o lanza RuntimeError."""
    ext = path.suffix.lower()
    if ext == ".pdf":  return _extraer_pdf(path)
    if ext == ".docx": return _extraer_docx(path)
    if ext == ".odt":  return _extraer_odt(path)
    if ext in {".txt", ".sql"}: return _extraer_txt(path)
    return ""


# ════════════════════════════════════════════════════════════════
# KEYWORDS
# ════════════════════════════════════════════════════════════════

def _extraer_keywords(texto: str, max_kw: int = 80) -> str:
    """
    Extrae las palabras más frecuentes (sin stop words) como keywords CSV.
    Sirve para acelerar el scoring sin releer todo el texto.
    """
    from backend.utils import extraer_palabras
    tokens = extraer_palabras(texto)
    # Frecuencia
    freq: dict[str, int] = {}
    for t in tokens:
        freq[t] = freq.get(t, 0) + 1
    # Top palabras por frecuencia
    top = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:max_kw]
    return ",".join(t for t, _ in top)


# ════════════════════════════════════════════════════════════════
# HASH RÁPIDO (primeros 64KB — suficiente para detectar cambios)
# ════════════════════════════════════════════════════════════════

def _hash_rapido(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        h.update(f.read(65536))
    return h.hexdigest()


# ════════════════════════════════════════════════════════════════
# INDEXACIÓN PRINCIPAL
# ════════════════════════════════════════════════════════════════

def indexar(docs_root: Path, limite: int | None = None, dry_run: bool = False) -> dict:
    """
    Recorre docs_root recursivamente e indexa documentos nuevos o modificados.

    Retorna stats: {nuevos, actualizados, sin_cambios, errores, eliminados}
    """
    if not docs_root.exists():
        logger.warning(f"DOCUMENTACION_ROOT no existe: {docs_root}")
        return {"error": f"Carpeta no encontrada: {docs_root}"}

    conn = get_connection()
    cur  = conn.cursor()

    # Cargar índice existente {ruta_str: (id, size, mtime, hash)}
    cur.execute(
        "SELECT id, ruta, size_bytes, modified_time, hash_contenido, estado "
        "FROM documentos_indexados"
    )
    indice_existente: dict[str, tuple] = {
        row[1]: row for row in cur.fetchall()
    }

    stats = {"nuevos": 0, "actualizados": 0, "sin_cambios": 0, "errores": 0, "eliminados": 0}
    procesados = 0

    # ── Recorrer filesystem ──────────────────────────────────────
    for fpath in sorted(docs_root.rglob("*")):
        if not fpath.is_file():
            continue
        if fpath.suffix.lower() not in EXTENSIONES_SOPORTADAS:
            continue
        if limite and procesados >= limite:
            logger.info(f"Límite de {limite} ficheros alcanzado.")
            break

        ruta_str      = str(fpath.resolve())
        carpeta_rel   = str(fpath.parent.relative_to(docs_root))
        nombre        = fpath.name
        extension     = fpath.suffix.lower()
        stat          = fpath.stat()
        size          = stat.st_size
        mtime         = stat.st_mtime

        existente = indice_existente.pop(ruta_str, None)

        if existente:
            _id, _size, _mtime, _hash, _estado = existente[0], existente[2], existente[3], existente[4], existente[5]
            # Sin cambios si size y mtime coinciden (rápido) o hash coincide
            sin_cambio = (size == _size and abs(mtime - (_mtime or 0)) < 1.0)
            if sin_cambio:
                stats["sin_cambios"] += 1
                # Reactivar si estaba marcado eliminado
                if _estado == "eliminado":
                    if not dry_run:
                        cur.execute(
                            "UPDATE documentos_indexados SET estado='activo', "
                            "fecha_actualizado=? WHERE id=?",
                            (datetime.now().isoformat(), _id)
                        )
                continue

        # ── Procesar documento nuevo o modificado ──────────────
        procesados += 1
        texto = ""
        error_msg = None
        estado = "activo"
        try:
            texto = extraer_texto(fpath)
        except RuntimeError as e:
            logger.error(f"Error extrayendo {fpath.name}: {e}")
            error_msg = str(e)
            estado = "error"

        keywords = _extraer_keywords(texto) if texto else ""
        hash_c   = _hash_rapido(fpath)
        ahora    = datetime.now().isoformat()

        if dry_run:
            accion = "NUEVO" if not existente else "ACTUALIZAR"
            logger.info(f"[dry-run] {accion}: {carpeta_rel}/{nombre}")
            if existente:
                stats["actualizados"] += 1
            else:
                stats["nuevos"] += 1
            continue

        if existente:
            cur.execute(
                """UPDATE documentos_indexados
                   SET nombre_archivo=?, extension=?, carpeta_relativa=?,
                       size_bytes=?, modified_time=?, hash_contenido=?,
                       texto_extraido=?, keywords=?, estado=?, error_msg=?,
                       fecha_actualizado=?
                   WHERE ruta=?""",
                (nombre, extension, carpeta_rel, size, mtime, hash_c,
                 texto, keywords, estado, error_msg, ahora, ruta_str)
            )
            stats["actualizados"] += 1
        else:
            cur.execute(
                """INSERT INTO documentos_indexados
                   (ruta, nombre_archivo, extension, carpeta_relativa,
                    size_bytes, modified_time, hash_contenido,
                    texto_extraido, keywords, estado, error_msg,
                    fecha_indexado, fecha_actualizado)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (ruta_str, nombre, extension, carpeta_rel,
                 size, mtime, hash_c, texto, keywords, estado, error_msg,
                 ahora, ahora)
            )
            stats["nuevos"] += 1

        if estado == "error":
            stats["errores"] += 1

    # ── Marcar como eliminados los que ya no existen en disco ───
    for ruta_str, row in indice_existente.items():
        if row[5] != "eliminado":  # estado
            stats["eliminados"] += 1
            if not dry_run:
                cur.execute(
                    "UPDATE documentos_indexados SET estado='eliminado', "
                    "fecha_actualizado=? WHERE ruta=?",
                    (datetime.now().isoformat(), ruta_str)
                )

    if not dry_run:
        conn.commit()
    conn.close()

    logger.info(f"Indexación completada: {stats}")
    return stats
