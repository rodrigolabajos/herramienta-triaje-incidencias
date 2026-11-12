# Soporte de Triaje de Incidencias

Sistema web de apoyo al triaje de incidencias mal asignadas. Combina búsqueda por similitud, trazas técnicas, documentación indexada e IA contextual para ayudar al personal de soporte a tomar decisiones mejor fundamentadas.

> **El sistema no decide automáticamente.** La decisión final siempre es humana.

---

## Funcionalidades

### Registro
- Alta de incidencias con descripción, departamento origen/destino y error.
- Trazas técnicas opcionales por incidencia.
- Importación masiva desde CSV.

### Consulta de triaje
- Búsqueda por descripción con filtros opcionales (error, departamento).
- Scoring ponderado de similitud contra el histórico.
- Recomendación de departamento por peso acumulado.
- Explicación en lenguaje natural generada por IA.
- Chat contextual con la IA sobre los resultados encontrados.

### Historial
- Listado paginado con filtros por texto y departamento.
- Exportación CSV.
- Acceso rápido a trazas y documentación relacionada desde cada fila.
- Comprobación de documentación en **una sola petición batch** por página (no N peticiones paralelas).

### Documentación relacionada
- Indexación incremental de documentación de soporte (PDF, DOCX, ODT, TXT, SQL).
- Asociación automática por scoring documental: keywords, nombre de fichero, carpeta, error y departamento.
- Caché en memoria de documentos indexados — el scoring no hace SELECT en cada request.
- Visualización desde consulta e historial: iframe para PDF, texto para el resto.
- Modal con score, motivo, preview y botón de descarga.

### Trazas técnicas
- Almacenamiento y visualización modal por incidencia.
- Vista visual (tabla de campos XML) y vista plana.
- Búsqueda dentro de trazas y copia al portapapeles.

### IA contextual
- Explicación breve de la recomendación de triaje.
- Chat contextual sobre la incidencia y evidencias similares.
- Trazas resumidas como evidencia principal (prioriza campos XML sobre stacktraces Java).
- **Acceso automático a documentación relacionada** cuando existe, sin consumir tokens si no la hay.
- Motor: [Groq](https://groq.com) con Llama 3.3 70B (rápido y gratuito con API key propia).

---

## Arquitectura

```
frontend/          HTML + CSS + JS sin frameworks
  css/
    style.css      Estilos globales (tokens, layout, componentes)
    documentacion.css  Modal y panel de documentación
    trazas-tree.css    Visualizador de trazas
  js/
    api.js         Constante API_BASE
    historial.js   Tabla paginada + batch-check de docs
    consulta.js    Búsqueda, scoring, IA
    documentacion.js  Modal de documentos relacionados
    trazas.js      Modal de trazas
    registrar.js   Formulario de alta
    dashboard.js   KPIs y gráficos

backend/
  api/
    incidencias.py     CRUD + export/import CSV
    busqueda.py        Scoring de similitud + chat IA
    documentacion.py   Documentos relacionados + batch-check
  services/
    ia.py              RAG compacto sobre Groq
    scoring.py         Lógica de similitud de incidencias
    similitud.py       Utilidades de comparación
    documentacion_indexer.py  Indexación incremental
  database/
    database.py        Conexión SQLite
    schema.sql         Esquema de tablas
  models/
    incidencias.py     Modelos Pydantic
  scripts/
    indexar_documentacion.py  Indexación desde CLI

documentacion/     Carpeta de documentos a indexar (no versionada)
run.py             Arranque automático con instalación de deps
```

### Optimizaciones de rendimiento
- **batch-check**: el historial hace 1 POST con los 20 IDs de la página; el backend responde `{id: bool}` usando la caché en memoria.
- **Caché de documentos**: `_docs_cache` carga los documentos indexados una vez por proceso; se invalida automáticamente al indexar.
- **Scoring sin texto completo**: la primera pasada usa solo `keywords + nombre + carpeta`; `texto_extraido` solo se trae para el preview de los ≤10 resultados finales (SUBSTR en SQL).
- **Índices SQLite**: `idx_doc_keywords` e `idx_doc_nombre` creados al arrancar.
- **asyncio.to_thread**: el scoring y el I/O de BD no bloquean el event loop de FastAPI.

---

## Ejecución

### Rápido (recomendado)

```bash
python run.py
```

Instala dependencias si faltan e inicia el servidor en `http://localhost:8000`.

### Manual

```bash
pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --reload
```

### Indexar documentación

```bash
# Automático al arrancar con run.py
python -m backend.scripts.indexar_documentacion

# Con opciones
python -m backend.scripts.indexar_documentacion --limite 100
python -m backend.scripts.indexar_documentacion --root ./documentacion
```

---

## Variables de entorno

Crear `.env` en la raíz del proyecto:

```env
GROQ_API_KEY=tu_api_key_de_groq
DOCUMENTACION_ROOT=./documentacion
ALLOWED_ORIGINS=http://localhost:8000
```

Sin `GROQ_API_KEY` el sistema funciona completamente salvo las funciones de IA.

---

## Endpoints principales

### Incidencias
| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/incidencias/` | Registrar incidencia |
| `GET` | `/incidencias/` | Listar con paginación y filtros |
| `DELETE` | `/incidencias/{id}` | Eliminar |
| `GET` | `/incidencias/{id}/trazas` | Trazas de una incidencia |
| `GET` | `/incidencias/export/csv` | Exportar todo a CSV |
| `POST` | `/incidencias/import/csv` | Importar desde CSV |

### Búsqueda e IA
| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/buscar/` | Búsqueda con scoring |
| `POST` | `/buscar/chat-contextual` | Chat IA con contexto |
| `GET` | `/buscar/stats` | Estadísticas generales |
| `GET` | `/buscar/chat-bbdd` | Pregunta libre sobre el histórico |

### Documentación
| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/documentacion/incidencia/{id}` | Docs relacionados con scoring |
| `POST` | `/documentacion/batch-check` | Check masivo para el historial |
| `GET` | `/documentacion/ver/{id}` | Servir fichero original |
| `GET` | `/documentacion/texto/{id}` | Texto extraído |
| `POST` | `/documentacion/indexar` | Indexación manual |

---

## Notas

- `.env` y `triage.db` no deben subirse al repositorio (están en `.gitignore`).
- La carpeta `documentacion/` puede contener subcarpetas; el indexador las recorre recursivamente.
- El sistema de scoring documental no requiere embeddings ni modelos externos: opera sobre texto normalizado y keywords extraídas en el momento de indexar.
