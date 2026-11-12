# Arquitectura

## Visión general

El proyecto está organizado en una arquitectura simple y modular que separa el frontend, el backend, la persistencia de datos y la lógica de IA.

## Frontend

- Ubicado en `frontend/`.
- Usa HTML estático, CSS personalizado y JavaScript puro.
- Consume la API REST expuesta por FastAPI.
- Páginas principales:
  - `index.html` - página de inicio.
  - `consulta.html` - búsqueda de incidencias similares y recomendaciones.
  - `registrar.html` - formulario para registrar nuevas incidencias.

## Backend

- Ubicado en `backend/`.
- Está implementado con FastAPI y expone rutas en `/incidencias` y `/buscar`.
- Monta el frontend estático en la ruta `/ui`.
- Inicializa la base de datos SQLite al arrancar.

## Persistencia

- Base de datos SQLite ubicada en `backend/triage.db`.
- Esquema definido en `backend/database/schema.sql`.
- Las operaciones de datos se realizan desde `backend/database/database.py`.

## Lógica de similitud y scoring

- `backend/services/similitud.py` calcula el score de coincidencia entre la descripción consultada y las incidencias históricas.
- El score pondera:
  - 60% la similitud de la descripción.
  - 25% coincidencia del código de error (si se suministra).
  - 15% coincidencia del departamento origen (si se filtra).
- `backend/services/scoring.py` agrega los scores para recomendar el departamento con mayor peso acumulado y aplica un umbral dinámico de confianza.

## IA explicativa

- `backend/services/ia.py` ofrece una integración opcional con Groq mediante la API de chat.
- Genera:
  - una explicación breve del departamento recomendado,
  - respuestas a preguntas contextuales sobre la incidencia.
- Si no se configura la API key, el sistema devuelve un mensaje de IA no configurada, pero sigue funcionando.
