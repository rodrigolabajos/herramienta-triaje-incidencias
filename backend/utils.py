"""Funciones utilitarias compartidas entre módulos."""

import re
import unicodedata

WORD_PATTERN = re.compile(r"\w+", re.UNICODE)


def normalizar(texto: str) -> str:
    """Normaliza texto: minúsculas, sin acentos, espacios."""
    texto = texto or ""
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(ch for ch in texto if not unicodedata.combining(ch))

STOP_WORDS = {
    "el", "la", "los", "las", "un", "una", "unos", "unas",
    "de", "del", "en", "con", "por", "para", "que", "se",
    "no", "es", "al", "lo", "le", "su", "sus", "a", "y",
    "o", "e", "ni", "pero", "si", "como", "cuando", "donde",
    "ha", "han", "he", "has", "hay", "ser", "esta", "este",
    "esto", "son", "fue", "era", "siendo", "tiene", "tienen"
}

def extraer_palabras(texto: str) -> list[str]:
    """Extrae palabras normalizadas del texto, filtrando stop words."""
    texto = normalizar(texto)
    tokens = WORD_PATTERN.findall(texto)
    # Filtra tokens cortos (<=2 chars) y stop words
    return [t for t in tokens if len(t) > 2 and t not in STOP_WORDS]