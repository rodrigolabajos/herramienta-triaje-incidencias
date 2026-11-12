from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from backend.api import incidencias, busqueda, documentacion
from backend.database.database import init_db

import os

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:8000").split(",")


# ✅ 1. Lifespan (sustituye @app.on_event deprecated)
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


# ✅ 2. Crear la app
app = FastAPI(
    title="Triage App API",
    description="Panel de soporte al triaje de incidencias — PoC",
    version="1.0.0",
    lifespan=lifespan
)

# ✅ 3. CORS (PoC)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)

# ✅ 4. Routers
app.include_router(
    incidencias.router,
    prefix="/incidencias",
    tags=["incidencias"]
)

app.include_router(
    busqueda.router,
    prefix="/buscar",
    tags=["busqueda"]
)

app.include_router(
    documentacion.router,
    prefix="/documentacion",
    tags=["documentacion"]
)

# ✅ 5. Redirecciones para rutas amigables
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/ui/index.html")

@app.get("/index", include_in_schema=False)
def index_redirect():
    return RedirectResponse(url="/ui/index.html")

@app.get("/consulta", include_in_schema=False)
def consulta_redirect():
    return RedirectResponse(url="/ui/consulta.html")

@app.get("/registrar", include_in_schema=False)
def registrar_redirect():
    return RedirectResponse(url="/ui/registrar.html")

@app.get("/historial", include_in_schema=False)
def historial_redirect():
    return RedirectResponse(url="/ui/historial.html")

'''
@app.get("/dashboard", include_in_schema=False)
def dashboard_redirect():
    return RedirectResponse(url="/ui/dashboard.html")
'''

# ✅ 6. Servir frontend estático en /ui
app.mount(
    "/ui",
    StaticFiles(directory="frontend", html=True),
    name="frontend"
)
