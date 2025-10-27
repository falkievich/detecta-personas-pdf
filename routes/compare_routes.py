"""
Router de FastAPI que expone el endpoint POST /upload_files para recibir un archivo de datos
(.json o .txt) y un PDF, guarda ambos en ficheros temporales, invoca la función de comparación
devuelve los resultados estructurados en JSON.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Body
from fastapi.responses import JSONResponse

from funcs.pdf_file_handler import procesar_pdf_y_comparar
from funcs.detectar_personas_pdf import detectar_personas_dni_matricula

#---------------------------------------------------------- Router
router = APIRouter(tags=["Analizador PDF: detección de personas e identificación; Comparador opcional con JSON/TXT"]) 

# ---------------------------------------------------------- Post - Cargar un archivo JSON y un PDF para realizar la comparación de valores
@router.post("/upload_files", summary=(
        "Analiza un archivo PDF para extraer personas e identificadores (DNI, CUIL, CUIT, Matrícula, etc.). "
        "Si solo se proporciona un PDF, detecta y devuelve las personas encontradas. "
        "Si además se adjunta un archivo .txt o .json, realiza la extracción anterior "
        "y compara los datos del archivo adjunto con la información detectada en el PDF."
    ))
async def compare(
    data_file: UploadFile | None = File(None, description="Archivo de datos opcional (.json, .txt)"),
    pdf_file: UploadFile | None = File(None, description="Archivo PDF (requerido)")
):
    """
    Endpoint que delega toda la lógica de procesamiento
    al módulo pdf_file_handler.
    """
    result = await procesar_pdf_y_comparar(pdf_file, data_file)
    return JSONResponse(result)

# ---------------------------------------------------------- Post - Detectar Nombre+Dni o Nombre+Matrícula 
@router.post("/detect_phrase", summary="Detectar Nombres + DNI, Matrícula, CUIL, etc; A partir de texto libre")
async def detect_personas(
    payload: dict = Body(..., description="JSON con { 'text': '<frase o párrafo>' }")
):
    text = payload.get("text", "")
    if not isinstance(text, str) or not text.strip():
        raise HTTPException(400, "Se requiere el campo 'text' con la frase a analizar")

    try:
        resultado = detectar_personas_dni_matricula(raw_text=text)
    except ValueError as e:
        raise HTTPException(400, str(e))

    return JSONResponse({"detected": resultado})