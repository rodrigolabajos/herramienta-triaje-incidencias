"""Módulo de acceso a datos SQLite."""

import sqlite3
from pathlib import Path
from backend.utils import normalizar, extraer_palabras

BASE_DIR   = Path(__file__).resolve().parent
DB_PATH    = BASE_DIR / "triage.db"
SCHEMA_PATH = BASE_DIR / "schema.sql"


def get_connection():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        cursor.executescript(f.read())
    conn.commit()
    conn.close()


def insertar_incidencia(data):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT INTO incidencias
               (id_incidencia, depto_origen, descripcion, depto_asignado, error, trazas)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (data.id_incidencia, data.departamento_origen,
             data.descripcion, data.departamento_asignado, data.error, data.trazas)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def buscar_incidencias(descripcion, limit=50):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        palabras = [p for p in extraer_palabras(descripcion) if len(p) > 2]
        if not palabras:
            return []
        condiciones = ["LOWER(descripcion) LIKE ?" for _ in palabras]
        params      = [f"%{p}%" for p in palabras]
        cursor.execute(
            f"SELECT id_incidencia, depto_origen, descripcion, depto_asignado, error, trazas, fecha_registro "
            f"FROM incidencias WHERE {' OR '.join(condiciones)} LIMIT ?",
            params + [limit]
        )
        resultados = cursor.fetchall()
        if resultados:
            return resultados
        # Fallback Python
        query_tokens = set(palabras)
        def tok(qt, tt):
            return qt == tt or qt.startswith(tt) or qt.endswith(tt) or tt.startswith(qt) or tt.endswith(qt)
        cursor.execute(
            "SELECT id_incidencia, depto_origen, descripcion, depto_asignado, error, trazas, fecha_registro FROM incidencias LIMIT ?",
            (limit,)
        )
        fb = [f for f in cursor.fetchall()
              if any(tok(qt, tt) for qt in query_tokens for tt in extraer_palabras(f[2]))]
        return fb[:limit]
    finally:
        conn.close()


def contar_incidencias() -> int:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM incidencias")
        return cursor.fetchone()[0]
    finally:
        conn.close()


def listar_incidencias():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""SELECT id, id_incidencia, depto_origen, descripcion,
                                 depto_asignado, error, fecha_registro, trazas
                          FROM incidencias ORDER BY fecha_registro DESC""")
        return cursor.fetchall()
    finally:
        conn.close()


def eliminar_incidencia(id_incidencia: str) -> int:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM incidencias WHERE id_incidencia = ?", (id_incidencia,))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def listar_incidencias_paginadas(limit: int, offset: int,
                                  departamento: str | None = None,
                                  buscar: str | None = None):
    conn = get_connection()
    try:
        cursor     = conn.cursor()
        conds, params = [], []
        if departamento:
            conds.append("depto_asignado = ?")
            params.append(departamento)
        if buscar:
            conds.append("(LOWER(id_incidencia) LIKE ? OR LOWER(descripcion) LIKE ?)")
            params += [f"%{buscar.lower()}%", f"%{buscar.lower()}%"]
        where = ("WHERE " + " AND ".join(conds)) if conds else ""
        cursor.execute(
            f"""SELECT id, id_incidencia, depto_origen, descripcion, depto_asignado,
                       error, fecha_registro,
                       CASE WHEN trazas IS NOT NULL AND trazas != '' 
                            THEN 1 ELSE 0 END as tiene_trazas
                FROM incidencias
                {where}
                ORDER BY fecha_registro DESC
                LIMIT ? OFFSET ?""",
            params + [limit, offset]
        )
        filas = cursor.fetchall()
        cursor.execute(f"SELECT COUNT(*) FROM incidencias {where}", params)
        total = cursor.fetchone()[0]
        return filas, total
    finally:
        conn.close()


def get_dashboard_stats():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM incidencias")
        total = cur.fetchone()[0]

        cur.execute("SELECT depto_asignado, COUNT(*) c FROM incidencias GROUP BY depto_asignado ORDER BY c DESC")
        por_depto = [{"departamento": r[0], "total": r[1]} for r in cur.fetchall()]

        cur.execute("""SELECT depto_origen, depto_asignado, COUNT(*) c
                       FROM incidencias WHERE depto_origen != depto_asignado
                       GROUP BY depto_origen, depto_asignado ORDER BY c DESC LIMIT 10""")
        flujos = [{"origen": r[0], "asignado": r[1], "total": r[2]} for r in cur.fetchall()]

        cur.execute("""SELECT DATE(fecha_registro) dia, COUNT(*) c
                       FROM incidencias WHERE fecha_registro >= DATE('now','-30 days')
                       GROUP BY dia ORDER BY dia""")
        evolucion = [{"dia": r[0], "total": r[1]} for r in cur.fetchall()]

        cur.execute("""SELECT error, COUNT(*) c FROM incidencias
                       WHERE error IS NOT NULL AND error != ''
                       GROUP BY error ORDER BY c DESC LIMIT 8""")
        top_errores = [{"error": r[0], "total": r[1]} for r in cur.fetchall()]

        return {"total": total, "por_departamento": por_depto,
                "flujos_reasignacion": flujos, "evolucion": evolucion,
                "top_errores": top_errores}
    finally:
        conn.close()

def obtener_trazas(id_incidencia: str):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT trazas FROM incidencias WHERE id_incidencia = ?",
            (id_incidencia,)
        )
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        conn.close()