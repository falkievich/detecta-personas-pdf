"""
Router de FastAPI que expone el endpoint POST /upload_files para recibir un archivo de datos
(.json o .txt) y un PDF, guarda ambos en ficheros temporales, invoca la función de comparación
devuelve los resultados estructurados en JSON.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from service.pdf_file_handler import procesar_pdf_y_comparar
from funcs.detectar_personas_pdf import detectar_personas_dni_matricula

#---------------------------------------------------------- Router
router = APIRouter(tags=["Analizador PDF — Detección de personas y comparación de datos"])

# ---------------------------------------------------------- Post - Cargar un archivo JSON y un PDF para realizar la comparación de valores
@router.post("/upload_files", summary=("Extrae personas de PDF y compara con datos opcionales"))
async def compare(
    data_file: UploadFile | str | None = File(None, description="Archivo opcional (.json o .txt) con datos para comparar. Si se omite, solo se extraen personas del PDF."),
    pdf_file: UploadFile = File(..., description="Archivo PDF a analizar (obligatorio).")
):
    """
    Recibe un PDF y, opcionalmente, un archivo de datos (.json o .txt).

    El flujo incluye:
      - Validación y guardado temporal de los ficheros.
      - Extracción de nombres e identificadores del PDF (DNI, CUIL, CUIT, Matrícula).
      - Si se proporciona `data_file`, realizará una comparación entre los datos extraídos y los datos entregados.
      - Devuelve un JSON estructurado con los resultados de la extracción y, si aplica, la comparación.
    """
    # Swagger UI, al marcar 'Send empty value', envía una cadena vacía para el campo file.
    # FastAPI espera UploadFile o None; normalizamos "" a None para evitar errores de validación.
    if isinstance(data_file, str):
        if data_file == "":
            data_file = None
        else:
            # Si por alguna razón se recibe otra cadena, ignorarla y tratar como None
            data_file = None

    result = await procesar_pdf_y_comparar(pdf_file, data_file)
    return JSONResponse(result)

# ---------------------------------------------------------- Post - Detectar Nombre+Dni o Nombre+Matrícula 
# Modelo para la entrada del endpoint /detect_phrase
class TextPayload(BaseModel):
    text: str = Field(..., description="Frase o párrafo a analizar")

@router.post("/detect_phrase", summary="Extrae nombres e identificadores desde texto")
async def detect_personas(
    payload: TextPayload = Body(..., description="JSON con la clave 'text' que contiene la frase o párrafo a analizar")
):
    """
    Analiza una frase o párrafo y extrae nombres e identificadores (DNI, Matrícula, CUIL, CUIT).

    Valida la entrada (campo 'text' obligatorio) y devuelve
    un JSON con los resultados.
    """
    text = payload.text
    try:
        resultado = detectar_personas_dni_matricula(raw_text=text)
    except ValueError as e:
        raise HTTPException(400, str(e))

    return JSONResponse({"detected": resultado})