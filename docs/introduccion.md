# Introducción

`TriajeVN` es un sistema web de soporte para el triaje de incidencias mal asignadas. Está diseñado como una prueba de concepto (PoC) para ayudar al personal de soporte a:

- registrar incidencias históricas con triaje correcto,
- buscar incidencias similares por descripción,
- recomendar un departamento de destino en función de similitud ponderada,
- ofrecer una explicación en lenguaje natural sobre la recomendación,
- permitir una consulta contextual opcional a una IA.

## Propósito

El proyecto no está destinado a tomar decisiones automáticas. Su objetivo es apoyar a los usuarios con recomendaciones y explicaciones, dejando la decisión final en manos de una persona.

## Componentes principales

- `frontend/` - interfaz de usuario estática con HTML, CSS y JavaScript.
- `backend/` - API en Python con FastAPI.
- `backend/database/` - acceso a datos SQLite y esquema de base de datos.
- `backend/services/` - lógica de similitud, scoring y conexión con IA.
- `docs/` - documentación del proyecto en español.
