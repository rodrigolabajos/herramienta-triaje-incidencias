# Documentación de la API

La API se divide en dos grupos principales de rutas:

- `/incidencias` - gestión de incidencias.
- `/buscar` - búsqueda de incidencias similares y recomendación.

## Rutas de `incidencias`

### POST `/incidencias/`

Registra una incidencia nueva.

**Body** (JSON):

- `id_incidencia` (string, mínimo 3 caracteres)
- `departamento_origen` (string, uno de los departamentos válidos)
- `descripcion` (string, mínimo 10 caracteres)
- `departamento_asignado` (string, uno de los departamentos válidos)
- `error` (string, opcional)
- `trazas` (string, opcional)

**Respuesta exitosa** (201):

```json
{
  "ok": true,
  "id": 1,
  "id_incidencia": "INC-123",
  "mensaje": "Incidencia registrada correctamente"
}
```

### GET `/incidencias/`

Lista incidencias con paginación.

Parámetros de consulta:

- `limit` (int, opcional, 1-100, por defecto 20)
- `offset` (int, opcional, por defecto 0)

**Respuesta**:

```json
{
  "total": 42,
  "limit": 20,
  "offset": 0,
  "incidencias": [ ... ]
}
```

### DELETE `/incidencias/{id_incidencia}`

Elimina una incidencia por su identificador.

**Respuesta exitosa**:

```json
{
  "ok": true,
  "mensaje": "Incidencia INC-123 eliminada"
}
```

## Rutas de `buscar`

### GET `/buscar/`

Busca incidencias similares usando la descripción.

Parámetros de consulta:

- `descripcion` (string, obligatorio, mínimo 3 caracteres)
- `error` (string, opcional)
- `departamento` (string, opcional)
- `pregunta` (string, opcional)

**Respuesta**:

```json
{
  "total": 5,
  "departamento_recomendado": "Documentos",
  "confianza": 0.68,
  "explicacion_ia": "...",
  "resultados": [
    {
      "id_incidencia": "INC-987",
      "departamento_origen": "CAU",
      "descripcion": "Fallo en la carga de facturas",
      "departamento_asignado": "Documentos",
      "error": "ERR-12",
      "score": 0.78
    }
  ]
}
```

Si se proporciona `pregunta`, la respuesta puede incluir también `respuesta_ia`.

### GET `/buscar/stats`

Devuelve estadísticas básicas del sistema.

**Respuesta**:

```json
{
  "total_incidencias": 42
}
```

## Seguridad y validaciones

- Los departamentos válidos están definidos en `backend/models/incidencias.py`.
- Si se intenta registrar una incidencia con un `id_incidencia` ya existente, la API devuelve un error 409.
- Si no hay datos suficientes o la confianza no alcanza el umbral dinámico, la recomendación de departamento puede ser `null`.
