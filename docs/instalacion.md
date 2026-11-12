# Instalación

## Requisitos

- Python 3.11 o superior
- pip
- Conexión a Internet solo para instalar dependencias y, opcionalmente, para el servicio de IA

## Instalación rápida

Desde la carpeta raíz del proyecto, ejecuta:

```bash
python run.py
```

Este script instala automáticamente las dependencias listadas en `backend/requirements.txt` y arranca el servidor en `http://localhost:8000`.

## Instalación manual

1. Abre una terminal y sitúate en la carpeta raíz del proyecto:

```bash
cd c:\Users\6003852\Desktop\TriajeVN
```

2. Crea un entorno virtual:

```bash
python -m venv venv
```

3. Activa el entorno virtual:

```bash
venv\Scripts\activate
```

4. Instala dependencias:

```bash
pip install -r backend\requirements.txt
```

5. Inicia el servidor:

```bash
python -m uvicorn backend.main:app --reload
```

6. Abre la aplicación en tu navegador:

```text
http://localhost:8000
```

## Variables de entorno opcionales

Si quieres habilitar las funciones de IA, crea un archivo `.env` en la raíz del proyecto con la variable:

```text
GROQ_API_KEY=tu_api_key_aqui
```

Si no se configura `GROQ_API_KEY`, la aplicación seguirá funcionando, pero los textos explicativos generados por la IA mostrarán un mensaje de "IA no configurada." o un error de generación.

## Dependencias principales

- `fastapi`
- `uvicorn`
- `pydantic`
- `httpx`
- `python-dotenv`
