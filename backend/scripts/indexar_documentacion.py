"""
Script de indexación incremental de documentación.

Uso:
    python -m backend.scripts.indexar_documentacion
    python -m backend.scripts.indexar_documentacion --limite 100
    python -m backend.scripts.indexar_documentacion --dry-run
    python -m backend.scripts.indexar_documentacion --root /ruta/absoluta/a/docs
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# Añadir raíz del proyecto al path para imports relativos
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=True)

from backend.database.database import init_db
from backend.services.documentacion_indexer import indexar

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)


def _resolver_root(root_arg: str | None) -> Path:
    """Resuelve DOCUMENTACION_ROOT desde argumento, env o .env."""
    raw = root_arg or os.getenv("DOCUMENTACION_ROOT", "./documentacion")
    p = Path(raw)
    if not p.is_absolute():
        # Relativa a la raíz del proyecto (dos niveles sobre /backend/scripts/)
        p = (Path(__file__).resolve().parents[2] / p).resolve()
    return p


def main():
    parser = argparse.ArgumentParser(description="Indexador incremental de documentación TriajeVN")
    parser.add_argument("--root",    type=str, default=None,  help="Ruta raíz de documentación (sobreescribe .env)")
    parser.add_argument("--limite",  type=int, default=None,  help="Límite de ficheros a procesar por ejecución")
    parser.add_argument("--dry-run", action="store_true",     help="Simula sin escribir en BBDD")
    args = parser.parse_args()

    docs_root = _resolver_root(args.root)
    logger.info(f"DOCUMENTACION_ROOT → {docs_root}")
    logger.info(f"Dry-run: {args.dry_run}  |  Límite: {args.limite or 'sin límite'}")

    # Asegurar que la tabla existe
    init_db()

    stats = indexar(docs_root=docs_root, limite=args.limite, dry_run=args.dry_run)

    print("\n── Resultado de indexación ──────────────────")
    for k, v in stats.items():
        print(f"  {k:15s}: {v}")
    print("─────────────────────────────────────────────\n")


if __name__ == "__main__":
    main()
