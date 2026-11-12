# Guía de uso

## Páginas principales

- `http://localhost:8000/ui/index.html` - página de acceso.
- `http://localhost:8000/ui/consulta.html` - búsqueda de incidencias similares y recomendación de departamento.
- `http://localhost:8000/ui/registrar.html` - formulario para registrar nuevas incidencias.

## Uso de la página de consulta

1. Introduce una descripción breve de la incidencia en el campo principal.
2. Haz clic en "Buscar".
3. El sistema mostrará:
   - departamento recomendado,
   - nivel de confianza,
   - explicación generada por la IA,
   - lista de incidencias históricas similares.
4. Si deseas, haz clic en la tarjeta de IA para preguntar algo específico sobre la incidencia.

### Notas del buscador

- El campo `descripcion` es obligatorio y debe tener al menos 3 caracteres.
- El sistema resalta las coincidencias encontradas en los resultados.
- Si no se encuentra un departamento con suficiente confianza, se mostrará un mensaje de advertencia.

## Uso de la página de registro

1. Completa los datos de la incidencia:
   - `id_incidencia`
   - `departamento_origen`
   - `descripcion`
   - `departamento_asignado`
   - `error` (opcional)
2. Envía el formulario para guardar la incidencia en la base de datos.
3. Si el `id_incidencia` ya existe, la API devolverá un error indicando que la incidencia ya existe.

## Ejemplos de uso directo con la API

### Buscar incidencias similares

```bash
curl "http://localhost:8000/buscar?descripcion=problema+de+facturación&error=ERR-123&departamento=CAU"
```

### Registrar una incidencia

```bash
curl -X POST "http://localhost:8000/incidencias/" \
  -H "Content-Type: application/json" \
  -d '{
    "id_incidencia": "INC-123",
    "departamento_origen": "CAU",
    "descripcion": "El cliente no puede cerrar su sesión",
    "departamento_asignado": "Hub Activo",
    "error": "ERR-401"
}'}
```

## Recomendaciones de uso

- Usa la búsqueda basada en descripción para aprovechar la lógica de similitud.
- Incluye el código de error y el departamento de origen cuando estén disponibles para mejorar la precisión.
- Revisa siempre la recomendación final: la decisión debe ser humana.
