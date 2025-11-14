import logging
import sys

# Configuración de logging global para ver DEBUG en uvicorn/fastapi
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
# Asegurar que los módulos relevantes estén en DEBUG
for _name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi", "starlette"):
    logging.getLogger(_name).setLevel(logging.DEBUG)

# Esto solo es para testar, Removerlo más adelante (línea 1 a la 13)

"""
Inicializa la aplicación FastAPI y monta el router que expone los endpoints para la comparación de datos JSON contra PDFs.
"""
from fastapi import FastAPI
from routes.compare_routes import router as compare_router
from routes.entity_extraction_routes import router as entity_extraction_router

app = FastAPI(title="API: Detección de Personas en PDF y Comparador con JSON/TXT")

# Router de nuestro endpoint
app.include_router(compare_router, prefix="/api")
app.include_router(entity_extraction_router, prefix="/api")

@app.get("/")
def read_root():
    return {"Hello": "World"}