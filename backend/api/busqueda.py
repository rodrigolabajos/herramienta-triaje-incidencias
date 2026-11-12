"""Rutas de API para búsqueda de incidencias y recomendaciones."""

from fastapi import APIRouter, Query
from typing import Optional
from collections import Counter
import asyncio
import time
import uuid

from pydantic import BaseModel

from backend.services.ia import (
    crear_contexto_ia,
    responder_chat_contextual_ligero
)

from backend.database.database import buscar_incidencias, contar_incidencias
from backend.services.similitud import calcular_score
from backend.services.scoring import departamento_recomendado

router = APIRouter()

CONTEXTOS_IA = {}
CONTEXTOS_TTL_SEGUNDOS = 30 * 60  # 30 minutos


class ChatContextualRequest(BaseModel):
    contexto_id: str
    pregunta: str
    historial: list | None = None


def _limpiar_contextos_expirados():
    ahora = time.time()
    expirados = [
        k for k, v in CONTEXTOS_IA.items()
        if ahora - v["created_at"] > CONTEXTOS_TTL_SEGUNDOS
    ]

    for k in expirados:
        CONTEXTOS_IA.pop(k, None)


def _nivel_confianza(confianza: float) -> str:
    if confianza >= 0.75:
        return "alta"
    if confianza >= 0.40:
        return "media"
    return "baja"


@router.get("/")
async def buscar(
    descripcion: str = Query(..., min_length=3),
    error: Optional[str] = Query(None),
    departamento: Optional[str] = Query(None),
):
    filas = await asyncio.to_thread(buscar_incidencias, descripcion)

    resultados = []

    for r in filas:
        # r esperado:
        # (id_incidencia, depto_origen, descripcion, depto_asignado, error, trazas, fecha_registro)
        incidencia = {
            "id_incidencia": r[0],
            "departamento_origen": r[1],
            "descripcion": r[2],
            "departamento_asignado": r[3],
            "error": r[4],
            "trazas": r[5],              # para crear contexto IA
            "tiene_trazas": bool(r[5]),  # para frontend
            "fecha_registro": r[6],
        }

        score = calcular_score(
            query_desc=descripcion,
            query_error=error,
            incidencia=incidencia,
            query_departamento=departamento
        )

        incidencia["score"] = score
        resultados.append(incidencia)

    resultados = [r for r in resultados if r["score"] > 0]
    resultados.sort(key=lambda x: x["score"], reverse=True)

    # Frontend: top 25 SIN trazas completas
    resultados_display = [
        {k: v for k, v in r.items() if k != "trazas"}
        for r in resultados[:25]
    ]

    resumen_global = None
    if resultados:
        deptos = [r["departamento_asignado"] for r in resultados]
        conteo = Counter(deptos).most_common(3)
        resumen_global = ", ".join(
            f"{d} ({n} casos)" for d, n in conteo
        )

    depto_rec = None
    confianza = 0.0
    nivel_confianza = "baja"
    explicacion = "No hay suficientes datos para generar una explicación."
    contexto_id = None

    # Primero calcular recomendación
    if resultados:
        depto_rec, confianza = departamento_recomendado(resultados)
        nivel_confianza = _nivel_confianza(confianza)

    if depto_rec and confianza >= 0.25:
        explicacion = (
            f"El sistema recomienda {depto_rec} con una confianza del "
            f"{round(confianza * 100)}% basándose en incidencias históricas similares."
        )

    # Después crear contexto IA con depto/confianza correctos
    if resultados:
        _limpiar_contextos_expirados()

        contexto_id = f"CTX-{uuid.uuid4().hex[:12]}"

        # Guardamos top 25 porque son los visibles.
        # La IA NO recibirá los 25; responder_chat_contextual_ligero seleccionará solo lo necesario.
        evidencias_contexto = resultados[:25]

        CONTEXTOS_IA[contexto_id] = {
            "created_at": time.time(),
            "contexto": crear_contexto_ia(
                descripcion=descripcion,
                depto=depto_rec,
                confianza=confianza,
                nivel_confianza=nivel_confianza,
                resultados=evidencias_contexto,
                resumen_global=resumen_global,
            )
        }

    respuesta = {
        "total": len(resultados),
        "departamento_recomendado": depto_rec,
        "confianza": confianza,
        "nivel_confianza": nivel_confianza,
        "explicacion_ia": explicacion,
        "resultados": resultados_display,
        "contexto_id": contexto_id
    }

    return respuesta


@router.post("/chat-contextual")
async def chat_contextual(payload: ChatContextualRequest):
    _limpiar_contextos_expirados()

    item = CONTEXTOS_IA.get(payload.contexto_id)

    if not item:
        return {
            "respuesta_ia": (
                "El contexto de esta consulta ha caducado. "
                "Vuelve a realizar la búsqueda para continuar."
            )
        }

    respuesta = await responder_chat_contextual_ligero(
        contexto=item["contexto"],
        pregunta=payload.pregunta,
        historial=payload.historial,
    )

    return {
        "respuesta_ia": respuesta
    }


@router.get("/stats")
async def estadisticas():
    total = await asyncio.to_thread(contar_incidencias)
    return {"total_incidencias": total}


@router.get("/chat-bbdd")
async def chat_con_bbdd(pregunta: str = Query(..., min_length=5)):
    """
    Permite hacer preguntas en lenguaje natural sobre toda la BBDD.
    Ejemplo: '¿Cuáles son los errores más frecuentes esta semana?'
    """
    from backend.services.ia import analizar_bbdd
    respuesta = await analizar_bbdd(pregunta)
    return {"pregunta": pregunta, "respuesta": respuesta}
