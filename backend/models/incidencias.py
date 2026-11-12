"""Modelo de datos Pydantic para validación de incidencias."""

from pydantic import BaseModel, Field, field_validator
from typing import Optional

DEPARTAMENTOS_VALIDOS = [
    "Hub Activo",
    "Particulares",
    "Automatizacion",
    "Documentos",
    "Precios",
    "Negocio",
    "CAU"
]

class IncidenciaCreate(BaseModel):
    id_incidencia: str = Field(..., min_length=3)
    departamento_origen: str
    descripcion: str = Field(..., min_length=10)
    departamento_asignado: str
    error: Optional[str] = None
    trazas: Optional[str] = None

    @field_validator("departamento_origen", "departamento_asignado")
    @classmethod
    def validar_departamento(cls, v):
        if v not in DEPARTAMENTOS_VALIDOS:
            raise ValueError(
                f"Departamento '{v}' no valido. Opciones: {', '.join(DEPARTAMENTOS_VALIDOS)}"
            )
        return v
