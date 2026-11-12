"""Reglas de agregación para recomendar un departamento.

Calcula el departamento con mayor peso acumulado a partir de los scores
de incidencias similares y aplica un umbral dinámico de confianza.
"""

def departamento_recomendado(resultados):
    if not resultados:
        return None, 0.0

    pesos = {}
    for r in resultados:
        depto = r["departamento_asignado"]
        pesos[depto] = pesos.get(depto, 0) + r["score"]

    if not pesos:
        return None, 0.0

    depto_final = max(pesos, key=pesos.get)
    total_score = sum(pesos.values())
    confianza = round(pesos[depto_final] / total_score if total_score else 0, 3)

    # ✅ UMBRAL DINÁMICO
    n = len(resultados)
    if n <= 3:
        umbral = 0.55
    elif n <= 8:
        umbral = 0.4
    else:
        umbral = 0.25

    if confianza < umbral:
        return None, confianza

    return depto_final, confianza
