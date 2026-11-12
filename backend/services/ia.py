"""
Servicio de IA — arquitectura RAG síncrono.

El backend consulta la BBDD ANTES de llamar a la IA y le pasa los datos
ya estructurados como contexto. Así el modelo nunca necesita ejecutar
herramientas ni exponer código/sintaxis interna.

Motor: Groq (Llama 3.3 70B) — rápido, gratuito, sin tarjeta
"""

import os
import re
import logging
import asyncio
import sqlite3
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Documentación relacionada (import tardío para evitar circular)
def _get_buscar_docs():
    from backend.api.documentacion import buscar_docs_relevantes_para_ia
    return buscar_docs_relevantes_para_ia


ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(ENV_PATH, override=True)

logger = logging.getLogger(__name__)

GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "").strip()
GROQ_URL       = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL     = "llama-3.3-70b-versatile"

DB_PATH = Path(__file__).resolve().parent.parent / "database" / "triage.db"

# ─────────────────────────────────────────────────────────────────────
# REGLAS FIJAS DEL SISTEMA
# ─────────────────────────────────────────────────────────────────────
_SYSTEM = (
    "Eres un asistente de soporte técnico para triaje de incidencias. "
    "REGLAS ESTRICTAS:\n"
    "1. Responde SIEMPRE en español.\n"
    "2. Responde de forma breve, clara y útil. Máximo 4 frases.\n"
    "3. Usa 'incidencias registradas' en vez de 'BBDD' o 'base de datos'.\n"
    "4. NUNCA escribas código, XML ni JSON en la respuesta final.\n"
    "5. NUNCA menciones herramientas internas ni cómo funciona el sistema.\n"
    "6. Si no tienes datos suficientes, di exactamente: No tengo datos suficientes para responderlo.\n"
    "7. Usa el resumen técnico de trazas como evidencia principal cuando esté disponible.\n"
    "8. En trazas mixtas, prioriza campos XML frente a logs Java o stacktraces.\n"
    "9. Si la confianza no es alta, indica que la recomendación no es definitiva.\n"
    "10. Puedes citar IDs de incidencias si aparecen en el contexto.\n"
    "11. No inventes datos fuera del contexto proporcionado."
)



# ─────────────────────────────────────────────────────────────────────
# CONSULTAS DE BBDD — Python las ejecuta, no la IA
# ─────────────────────────────────────────────────────────────────────

def _query(sql: str, params: tuple = ()) -> list:
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        conn.close()
        return rows
    except Exception as e:
        logger.warning(f"Query BBDD falló: {e}")
        return []


def _contexto_stats() -> str:
    total_rows = _query("SELECT COUNT(*) FROM incidencias")
    total = total_rows[0][0] if total_rows else 0

    deptos = _query(
        "SELECT depto_asignado, COUNT(*) c FROM incidencias "
        "GROUP BY depto_asignado ORDER BY c DESC"
    )
    errores = _query(
        "SELECT error, COUNT(*) c FROM incidencias "
        "WHERE error IS NOT NULL AND error != '' "
        "GROUP BY error ORDER BY c DESC LIMIT 5"
    )
    flujos = _query(
        "SELECT depto_origen, depto_asignado, COUNT(*) c FROM incidencias "
        "WHERE depto_origen != depto_asignado "
        "GROUP BY depto_origen, depto_asignado ORDER BY c DESC LIMIT 5"
    )

    partes = [f"Total incidencias registradas: {total}."]
    if deptos:
        d_str = ", ".join(f"{d}: {n}" for d, n in deptos)
        partes.append(f"Por departamento: {d_str}.")
    if errores:
        e_str = "; ".join(f'"{e[:50]}" ({n}x)' for e, n in errores)
        partes.append(f"Errores más frecuentes: {e_str}.")
    if flujos:
        f_str = "; ".join(f"{o}->{a} ({n}x)" for o, a, n in flujos)
        partes.append(f"Reasignaciones más comunes: {f_str}.")

    return "\n".join(partes)


def _normalizar_traza_html(traza: str) -> str:
    """
    Normaliza trazas para análisis interno:
    - Si vienen como &lt;TAG&gt;, las convierte a <TAG>.
    - Si vienen como &amp;lt;TAG&amp;gt;, también las convierte a <TAG>.
    - Si ya vienen como XML real <TAG>, las deja igual.
    """
    if not traza:
        return ""

    prev = None
    actual = str(traza)

    while actual != prev:
        prev = actual
        actual = (
            actual
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
        )

    return actual


def _extraer_campos_xml_relevantes(traza: str, max_campos: int = 25) -> list[tuple[str, str]]:
    """
    Extrae pares etiqueta/valor de XML embebido sin meter XML completo al modelo.
    Funciona tanto con XML real <TAG> como con XML escapado &lt;TAG&gt;.
    Prioriza campos útiles para diagnóstico.
    """
    texto = _normalizar_traza_html(traza)

    # Captura hojas simples: <TAG>valor</TAG>
    matches = re.findall(
        r"<([A-Za-z0-9_:-]+)>([^<>]{1,800})</\1>",
        texto,
        flags=re.DOTALL
    )


    if not matches:
        return []

    prioridad = {
        "COD_ERROR": 1,
        "DES_ERROR": 2,
        "ERROR": 3,
        "RESULTADO": 4,
        "ESTADO": 5,
        "HTTP_STATUS": 6,
        "SERVICIO": 7,
        "ORIGIN": 8,
        "ORIGEN_DIAGNOSTICO": 9,
        "FAMILIA_ERROR": 10,
        "MODULO_AFECTADO": 11,
        "DEPARTAMENTO_RECOMENDADO": 12,
        "DEP_ASIGNADO": 13,
        "DEP_ORIGEN": 14,
        "CONFIANZA_REFERENCIAL": 15,
        "CRITERIO_PRINCIPAL": 16,
        "DESCRIPCION_DIAGNOSTICO": 17,
        "DESCRIPCION_INCIDENCIA": 18,
        "ERROR_DECLARADO": 19,
        "ID_INCIDENCIA": 20,
        "ID_TRACE": 21,
        "REFERENCIA_TRAZA": 22,
        "REFERENCIA_OPERACION": 23,
        "CANAL": 24,
        "OPERACION": 25,
        "FECHA_EVENTO": 26,
        "DATOS_FICTICIOS": 900,
        "NO_CONTIENE_DATOS_REALES": 901,
    }

    campos = []

    for tag, valor in matches:
        valor_limpio = " ".join(valor.split())
        if not valor_limpio:
            continue

        if len(valor_limpio) > 300:
            valor_limpio = valor_limpio[:300] + "..."

        campos.append((tag, valor_limpio))

    campos.sort(key=lambda x: prioridad.get(x[0], 999))

    vistos = set()
    unicos = []

    for tag, valor in campos:
        k = (tag, valor)
        if k not in vistos:
            vistos.add(k)
            unicos.append((tag, valor))

    return unicos[:max_campos]


def _extraer_senales_java_compactas(traza: str, max_lineas: int = 3) -> list[str]:
    """
    Extrae solo señales Java/logs muy compactas.
    No mete stacktraces completos.
    """
    if not traza:
        return []

    lineas = []

    patrones = (
        "Exception",
        "ERROR",
        "WARN",
        "Caused by:",
        "Timeout",
        "timed out",
        "HTTP",
    )

    for linea in str(traza).splitlines():
        s = linea.strip()
        if not s:
            continue

        if any(p in s for p in patrones):
            # Evitar líneas enormes
            if len(s) > 220:
                s = s[:220] + "..."
            lineas.append(s)

        if len(lineas) >= max_lineas:
            break

    return lineas


def _resumen_traza_para_ia(traza: str) -> str:
    """
    Crea un resumen compacto de la traza para el LLM.
    Prioriza XML sobre Java.
    """
    if not traza:
        return "Sin trazas registradas."

    campos_xml = _extraer_campos_xml_relevantes(traza)
    senales_java = _extraer_senales_java_compactas(traza)

    partes = []

    if campos_xml:
        partes.append("Campos XML relevantes:")
        for tag, valor in campos_xml:
            partes.append(f"- {tag}: {valor}")

    if senales_java:
        partes.append("Señales Java/log compactas, secundarias frente al XML:")
        for s in senales_java:
            partes.append(f"- {s}")

    if not partes:
        partes.append("La traza existe, pero no se han detectado campos XML o señales técnicas relevantes.")

    return "\n".join(partes)



# ─────────────────────────────────────────────────────────────────────
# LIMPIEZA — elimina cualquier filtración de código o sintaxis interna
# ─────────────────────────────────────────────────────────────────────

def _limpiar(texto: str) -> str:
    lineas_ok = []
    for linea in texto.splitlines():
        s = linea.strip()
        # Descartar líneas con restos de tool calls o JSON crudo
        if re.search(r'<function[= ]|function=|tool_call', s):
            continue
        if s.startswith("{") or s.startswith("["):
            continue
        if re.search(r'"descripcion"\s*:', s) or re.search(r'"role"\s*:', s):
            continue
        # Lenguaje amigable
        linea = re.sub(r'\bBBDD\b', 'incidencias registradas', linea)
        linea = re.sub(r'\bbase de datos\b', 'incidencias registradas', linea, flags=re.IGNORECASE)
        if s:
            lineas_ok.append(linea)

    resultado = "\n".join(lineas_ok).strip()
    if len(resultado) < 8:
        return "No tengo datos suficientes para responder eso."
    return resultado


# ─────────────────────────────────────────────────────────────────────
# LLAMADA A GROQ
# ─────────────────────────────────────────────────────────────────────

async def _groq(messages: list, max_tokens: int) -> str:
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY no configurada")

    async with httpx.AsyncClient(timeout=25.0) as client:
        r = await client.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "messages": messages,
                "temperature": 0.15,
                "max_tokens": max_tokens,
            },
        )

        if r.status_code >= 400:
            raise RuntimeError(
                f"Groq HTTP {r.status_code} usando modelo {GROQ_MODEL}: {r.text[:1200]}"
            )

        data = r.json()

        try:
            content = data["choices"][0]["message"]["content"]
        except Exception:
            raise RuntimeError(f"Respuesta inesperada de Groq: {str(data)[:1200]}")

        return _limpiar(content)


async def _llamar(messages: list, max_tokens: int = 120) -> str:
    try:
        return await _groq(messages, max_tokens)

    except Exception as e:
        err = str(e)
        err_lower = err.lower()

        logger.error(f"Groq falló: {err[:1200]}")

        # 1) API key / autorización
        if (
            "groq_api_key no configurada" in err_lower
            or "401" in err
            or "unauthorized" in err_lower
            or "invalid api key" in err_lower
        ):
            return "No se pudo contactar con la IA. La API key de Groq no es válida o no está configurada."

        # 2) Límites de tokens / contexto / request demasiado grande
        if (
            "413" in err
            or "context_length" in err_lower
            or "context length" in err_lower
            or "maximum context" in err_lower
            or "too many tokens" in err_lower
            or "tokens" in err_lower
            or "request too large" in err_lower
            or "payload too large" in err_lower
            or "rate_limit_exceeded" in err_lower
            or "tokens per minute" in err_lower
        ):
            return (
                "La IA no puede responder porque el contexto enviado es demasiado grande "
                "o se ha alcanzado un límite de tokens. Reduce el número de evidencias o resume más las trazas."
            )

        # 3) Rate limit / cuota
        if (
            "429" in err
            or "rate limit" in err_lower
            or "rate_limit" in err_lower
            or "quota" in err_lower
            or "requests per minute" in err_lower
        ):
            return "La IA está ocupada ahora mismo o se ha alcanzado el límite de uso. Inténtalo en unos segundos."

        # 4) Modelo realmente inválido
        # OJO: no usamos simplemente "model" porque muchos errores mencionan el modelo.
        if (
            "model_not_found" in err_lower
            or "model not found" in err_lower
            or "does not exist" in err_lower
            or "invalid model" in err_lower
            or "not a valid model" in err_lower
        ):
            return f"No se pudo contactar con la IA. El modelo configurado no es válido: {GROQ_MODEL}"

        # 5) Fallback genérico
        return "No se pudo contactar con la IA. Revisa la configuración de Groq."


# ─────────────────────────────────────────────────────────────────────
# API PÚBLICA — mismas firmas que el archivo original
# ─────────────────────────────────────────────────────────────────────

async def analizar_bbdd(pregunta: str) -> str:
    stats = await asyncio.to_thread(_contexto_stats)

    messages = [
        {"role": "system", "content": _SYSTEM},
        {
            "role": "user",
            "content": (
                f"Datos de las incidencias registradas:\n{stats}\n\n"
                f"Pregunta: {pregunta}\n\n"
                "Responde en máximo 3 frases basándote solo en los datos anteriores."
            ),
        },
    ]
    return await _llamar(messages, max_tokens=200)

def crear_contexto_ia(
    descripcion: str,
    depto: str | None,
    confianza: float,
    nivel_confianza: str,
    resultados: list,
    resumen_global: str | None = None,
) -> dict:
    """
    Crea un contexto compacto reutilizable para el chat IA.
    No llama a Groq.
    No mete trazas completas.
    Guarda resúmenes técnicos compactos por incidencia.
    """
    evidencias = []

    for r in resultados:
        trazas = r.get("trazas") or ""
        resumen_traza = _resumen_traza_para_ia(trazas)

        if len(resumen_traza) > 1800:
            resumen_traza = resumen_traza[:1800] + "\n- Resumen recortado por tamaño."

        evidencias.append({
            "id": r.get("id_incidencia"),
            "score_pct": round(float(r.get("score", 0.0)) * 100),
            "departamento_asignado": r.get("departamento_asignado"),
            "departamento_origen": r.get("departamento_origen"),
            "fecha_registro": r.get("fecha_registro"),
            "descripcion": r.get("descripcion"),
            "error": r.get("error"),
            "tiene_trazas": bool(trazas),
            "resumen_traza": resumen_traza,
        })

    return {
        "descripcion": descripcion,
        "departamento_recomendado": depto,
        "confianza": round(confianza * 100),
        "nivel_confianza": nivel_confianza,
        "resumen_global": resumen_global,
        "evidencias": evidencias,
    }


def _seleccionar_evidencias_para_pregunta(contexto: dict, pregunta: str) -> list:
    """
    Selecciona solo las evidencias necesarias para esta pregunta.
    - Si el usuario menciona IDs concretos, usa esas evidencias.
    - Si no, usa las 3 primeras evidencias.
    """
    evidencias = contexto.get("evidencias", [])
    if not evidencias:
        return []

    ids_preguntados = set(
        re.findall(r"\bINC-[A-Za-z0-9_-]+\b", pregunta or "", flags=re.IGNORECASE)
    )
    ids_preguntados = {x.upper() for x in ids_preguntados}

    if ids_preguntados:
        seleccionadas = [
            e for e in evidencias
            if str(e.get("id", "")).upper() in ids_preguntados
        ]
        return seleccionadas

    return evidencias[:3]


def _formatear_evidencias_compactas(evidencias: list) -> str:
    if not evidencias:
        return "No hay evidencias disponibles para esta pregunta."

    bloques = []

    for i, e in enumerate(evidencias, start=1):
        resumen = e.get("resumen_traza") or "Sin resumen técnico de trazas."

        if len(resumen) > 1200:
            resumen = resumen[:1200] + "\n- Resumen recortado por tamaño."

        bloque = [
            f"EVIDENCIA {i}",
            f"ID: {e.get('id')}",
            f"Score de similitud: {e.get('score_pct')}%",
            f"Departamento histórico asignado: {e.get('departamento_asignado')}",
            f"Departamento origen: {e.get('departamento_origen')}",
            f"Fecha registro: {e.get('fecha_registro')}",
            f"Descripción: {e.get('descripcion')}",
            f"Error registrado: {e.get('error') or 'sin error'}",
            "Resumen técnico de trazas:",
            resumen,
        ]

        bloques.append("\n".join(bloque))

    return "\n\n".join(bloques)


async def responder_chat_contextual_ligero(
    contexto: dict,
    pregunta: str,
    historial: list | None = None,
) -> str:
    """
    Responde usando un contexto ya creado previamente.
    Accede a documentación relacionada solo cuando existe,
    usando el mismo scoring ligero del panel de docs (caché en memoria).
    """
    evidencias = _seleccionar_evidencias_para_pregunta(contexto, pregunta)
    evidencias_txt = _formatear_evidencias_compactas(evidencias)

    bloque_contexto = (
        f'Incidencia actual: "{contexto.get("descripcion")}"\n'
        f'Departamento recomendado: {contexto.get("departamento_recomendado") or "sin determinar"}\n'
        f'Confianza del sistema: {contexto.get("confianza")}% ({contexto.get("nivel_confianza")}).\n'
    )

    if contexto.get("resumen_global"):
        bloque_contexto += f'Resumen global: {contexto.get("resumen_global")}\n'

    bloque_contexto += (
        "\nEvidencias seleccionadas para esta pregunta:\n"
        f"{evidencias_txt}\n\n"
        "Instrucciones:\n"
        "- Responde solo usando estas evidencias.\n"
        "- Si el usuario pregunta por una ID concreta y aparece en evidencias, usa esa evidencia.\n"
        "- Prioriza los campos XML del resumen técnico de trazas frente a Java o stacktraces.\n"
        "- No copies XML ni código literal.\n"
        "- Si no hay evidencia suficiente, dilo claramente.\n"
    )

    # ── Documentación relacionada ──────────────────────────────
    # Se busca el id_incidencia de la primera evidencia relevante.
    # Se inyecta en el contexto SOLO si hay docs reales (no consume tokens si no hay).
    # Usa la caché en memoria — no hace ningún SELECT adicional.
    id_inc = None
    if evidencias:
        id_inc = evidencias[0].get("id")
    elif contexto.get("evidencias"):
        id_inc = contexto["evidencias"][0].get("id")

    if id_inc:
        try:
            buscar_docs = _get_buscar_docs()
            docs_ctx = await asyncio.to_thread(buscar_docs, id_inc, 1200)
            if docs_ctx:
                bloque_contexto += (
                    "\nDocumentación técnica relacionada con la incidencia "
                    "(úsala si el usuario pregunta sobre procedimientos, manuales o soluciones documentadas):\n"
                    f"{docs_ctx}\n"
                    "- Cita el nombre del documento si usas información de él.\n"
                    "- No copies fragmentos literales extensos.\n"
                )
        except Exception as e:
            logger.warning(f"No se pudo obtener docs para IA: {e}")
    # ──────────────────────────────────────────────────────────

    messages = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": bloque_contexto},
    ]

    if historial:
        for m in historial[-4:]:
            role = m.get("role", "")
            content = m.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": pregunta})

    return await _llamar(messages, max_tokens=180)