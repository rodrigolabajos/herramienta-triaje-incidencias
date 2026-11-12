"""
Uso: python run.py
- Instala las dependencias automáticamente si no están
- Indexa la documentación
- Arranca el servidor en http://localhost:8000
"""

import subprocess
import sys
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
REQUIREMENTS = os.path.join(ROOT, "backend", "requirements.txt")


def ejecutar_indexador_documentacion():
    """
    Ejecuta el indexador incremental de documentación antes de arrancar el servidor.
    Si falla, no detiene el arranque del backend.
    """
    print("📚 Indexando documentación...")

    try:
        subprocess.check_call(
            [sys.executable, "-m", "backend.scripts.indexar_documentacion"],
            cwd=ROOT
        )
        print("✅ Documentación indexada correctamente.\n")

    except subprocess.CalledProcessError as e:
        print("⚠️ Error al indexar documentación.")
        print(f"   Código de salida: {e.returncode}")
        print("   El servidor arrancará igualmente.\n")

    except Exception as e:
        print("⚠️ Error inesperado al indexar documentación.")
        print(f"   {e}")
        print("   El servidor arrancará igualmente.\n")


if os.environ.get("_TRIAJE_READY"):
    # Segunda ejecución: dependencias ya instaladas, indexar y arrancar servidor
    sys.path.insert(0, ROOT)

    ejecutar_indexador_documentacion()

    import uvicorn

    print("\n✅ Servidor arrancado → http://localhost:8000\n")
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=False)

else:
    # Primera ejecución: instalar dependencias y relanzar
    print("📦 Instalando dependencias...")

    subprocess.check_call([
        sys.executable,
        "-m",
        "pip",
        "install",
        "-r",
        REQUIREMENTS
    ])

    print("✅ Dependencias instaladas.\n")

    env = {**os.environ, "_TRIAJE_READY": "1"}

    subprocess.call(
        [sys.executable, __file__],
        env=env,
        cwd=ROOT
    )