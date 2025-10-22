"""
Inicializa la aplicación FastAPI y monta el router que expone los endpoints para la comparación de datos JSON contra PDFs.
"""
from fastapi import FastAPI
from routes.compare_routes import router as compare_router

app = FastAPI(title="API: Detección de Personas en PDF y Comparador con JSON/TXT")

# Router de nuestro endpoint
app.include_router(compare_router, prefix="/api")
