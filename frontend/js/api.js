/**
 * api.js — URL base automática
 *
 * Si el HTML se abre como file:// (desarrollo sin servidor),
 * apunta a http://localhost:8000.
 * Si lo sirve FastAPI (localhost:8000/ui/...), usa rutas relativas.
 */
const API_BASE = window.location.protocol === "file:"
  ? "http://localhost:8000"
  : "";
