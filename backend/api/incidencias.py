"""Rutas de API para gestionar incidencias."""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlite3 import IntegrityError
from typing import Optional, List
import csv, io

from backend.models.incidencias import IncidenciaCreate
from backend.database.database import (
    insertar_incidencia,
    listar_incidencias,
    listar_incidencias_paginadas,
    eliminar_incidencia,
    get_dashboard_stats,
    obtener_trazas,           
)

router = APIRouter()


@router.post("/", status_code=201)
async def registrar_incidencia(incidencia: IncidenciaCreate):
    try:
        nueva_id = insertar_incidencia(incidencia)
        return {"ok": True, "id": nueva_id,
                "id_incidencia": incidencia.id_incidencia,
                "mensaje": "Incidencia registrada correctamente"}
    except IntegrityError:
        raise HTTPException(status_code=409, detail="La incidencia ya existe")


# ⚠️  Rutas estáticas ANTES de /{id_incidencia} para que FastAPI no las confunda
@router.get("/stats/dashboard")
async def dashboard():
    return get_dashboard_stats()


@router.get("/export/csv")
async def exportar_csv():
    filas  = listar_incidencias()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "id_incidencia", "depto_origen", "descripcion",
                     "depto_asignado", "error", "fecha_registro", "trazas"])
    for f in filas:
        writer.writerow(f)
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=incidencias.csv"}
    )


@router.post("/import/csv", status_code=200)
async def importar_csv(filas: List[IncidenciaCreate]):
    insertadas, duplicadas, errores = 0, 0, []
    for inc in filas:
        try:
            insertar_incidencia(inc)
            insertadas += 1
        except IntegrityError:
            duplicadas += 1
        except Exception as e:
            errores.append(str(e))
    return {"insertadas": insertadas, "duplicadas": duplicadas, "errores": errores}


@router.get("/")
async def listar(
    limit:        int           = Query(20, ge=1, le=100),
    offset:       int           = Query(0,  ge=0),
    departamento: Optional[str] = Query(None),
    buscar:       Optional[str] = Query(None),
):
    filas, total = listar_incidencias_paginadas(limit, offset, departamento, buscar)
    return {
        "total": total, "limit": limit, "offset": offset,
        "incidencias": [
            {"id": f[0], "id_incidencia": f[1], "depto_origen": f[2],
             "descripcion": f[3], "depto_asignado": f[4],
             "error": f[5], "fecha_registro": f[6], "tiene_trazas": bool(f[7])}
            for f in filas
        ],
    }

@router.get("/{id_incidencia}/trazas")
async def get_trazas(id_incidencia: str):
    xml = obtener_trazas(id_incidencia)
    if xml is None:
        raise HTTPException(status_code=404, detail="Incidencia no encontrada")
    return {"id_incidencia": id_incidencia, "trazas": xml}

@router.delete("/{id_incidencia}", status_code=200)
async def eliminar(id_incidencia: str):
    if eliminar_incidencia(id_incidencia) == 0:
        raise HTTPException(status_code=404, detail="Incidencia no encontrada")
    return {"ok": True, "mensaje": f"Incidencia {id_incidencia} eliminada"}
