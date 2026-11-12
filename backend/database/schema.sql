-- Esquema de la base de datos SQLite para almacenar incidencias triadas.
CREATE TABLE IF NOT EXISTS incidencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_incidencia TEXT NOT NULL UNIQUE,
    depto_origen TEXT NOT NULL,
    descripcion TEXT NOT NULL,
    depto_asignado TEXT NOT NULL,
    error TEXT,
    trazas TEXT,
    fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_depto_asignado
ON incidencias(depto_asignado);

CREATE INDEX IF NOT EXISTS idx_descripcion
ON incidencias(descripcion);
-- Índice incremental de documentos de soporte
CREATE TABLE IF NOT EXISTS documentos_indexados (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    ruta             TEXT    NOT NULL UNIQUE,     -- ruta absoluta (solo backend)
    nombre_archivo   TEXT    NOT NULL,
    extension        TEXT    NOT NULL,
    carpeta_relativa TEXT,                        -- ruta relativa a DOCUMENTACION_ROOT
    size_bytes       INTEGER,
    modified_time    REAL,
    hash_contenido   TEXT,
    texto_extraido   TEXT,
    keywords         TEXT,                        -- tokens clave extraídos del texto
    estado           TEXT    DEFAULT 'activo',    -- activo | error | eliminado
    error_msg        TEXT,
    fecha_indexado   TEXT    DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizado TEXT
);

CREATE INDEX IF NOT EXISTS idx_doc_estado    ON documentos_indexados(estado);
CREATE INDEX IF NOT EXISTS idx_doc_extension ON documentos_indexados(extension);
