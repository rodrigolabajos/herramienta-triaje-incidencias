"""Lógica de similitud y scoring de incidencias.

Este módulo calcula qué tan parecida es una incidencia histórica a una
consulta de descripción y aplica pesos adicionales por código de error y
coincidencia de departamento.
"""

from backend.utils import normalizar, extraer_palabras

# Alias para compatibilidad
def extraer_tokens(texto: str) -> list[str]:
    """Alias para extraer_palabras (mantiene compatibilidad)."""
    return extraer_palabras(texto)


def tokens_coincidentes(q_tokens: set[str], t_tokens: set[str]) -> set[str]:
    coincidencias = set()
    for qt in q_tokens:
        for tt in t_tokens:
            if qt == tt or qt in tt or tt in qt:
                coincidencias.add(qt)
                break
    return coincidencias


def similitud_descripcion(query: str, texto: str) -> float:
    """
    Similitud basada en coincidencias de tokens y variantes parciales.
    """
    q_tokens = set(extraer_tokens(query))
    t_tokens = set(extraer_tokens(texto))

    if not q_tokens or not t_tokens:
        return 0.0

    interseccion = tokens_coincidentes(q_tokens, t_tokens)
    union = q_tokens | t_tokens

    return len(interseccion) / len(union)


def calcular_score(
    query_desc: str,
    query_error: str | None,
    incidencia: dict,
    query_departamento: str | None = None
) -> float:
    """
    Score total ponderado:
    - 60% similitud de descripción
    - 25% coincidencia de código de error (si existe)
    - 15% coincidencia de departamento origen (solo si se filtra)
    """

    score = 0.0

    # 1️⃣ Similitud de descripción (peso principal)
    score += 0.60 * similitud_descripcion(
        query_desc,
        incidencia.get("descripcion", "")
    )

    # 2️⃣ Coincidencia de error (opcional)
    if query_error and incidencia.get("error"):
        if query_error.lower() in incidencia["error"].lower():
            score += 0.25

    # 3️⃣ Coincidencia de departamento origen — solo bonus
    if query_departamento and incidencia.get("departamento_origen"):
        if query_departamento.lower() == incidencia["departamento_origen"].lower():
            score += 0.15

    return round(score, 4)