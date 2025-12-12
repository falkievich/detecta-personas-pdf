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
@router.post("/upload_files", summary=("Extrae personas de PDF o TXT y compara con datos opcionales"))
async def compare(
    data_file: UploadFile | str | None = File(None, description="Archivo opcional (.json o .txt) con datos para comparar. Si se omite, solo se extraen personas."),
    pdf_file_main: UploadFile | None = File(None, description="Archivo PDF principal a analizar (requerido si no se proporciona txt_file_main)."),
    txt_file_main: UploadFile | None = File(None, description="Archivo TXT principal a analizar (alternativa a pdf_file_main).")
):
    """
    Recibe un PDF o TXT y, opcionalmente, un archivo de datos (.json o .txt).

    El flujo incluye:
      - Validación de que se proporcione exactamente uno de: pdf_file_main o txt_file_main.
      - Validación y guardado temporal de los ficheros.
      - Extracción de nombres e identificadores (DNI, CUIL, CUIT, Matrícula).
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

    # Validar que se proporcione exactamente uno de pdf_file_main o txt_file_main
    pdf_provided = pdf_file_main is not None and getattr(pdf_file_main, "filename", None)
    txt_provided = txt_file_main is not None and getattr(txt_file_main, "filename", None)
    
    if not pdf_provided and not txt_provided:
        raise HTTPException(
            status_code=400,
            detail="Debe proporcionar un archivo PDF (pdf_file_main) o un archivo TXT (txt_file_main)."
        )
    
    if pdf_provided and txt_provided:
        raise HTTPException(
            status_code=400,
            detail="Solo debe proporcionar uno de: pdf_file_main o txt_file_main, no ambos."
        )

    result = await procesar_pdf_y_comparar(pdf_file_main, data_file, txt_file_main)
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