"""
Router de FastAPI que expone el endpoint POST /upload_files para recibir un archivo de datos
(.json o .txt) y un PDF, guarda ambos en ficheros temporales, invoca la función de comparación
devuelve los resultados estructurados en JSON.
"""
import os
import tempfile

from fastapi import APIRouter, UploadFile, File, HTTPException, Body
from fastapi.responses import JSONResponse

from funcs.comparar_json_pdf import comparar_valores_json_pdf
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
    # Validaciones iniciales
    # Comprobación explícita cuando no se sube ningún archivo PDF
    if pdf_file is None or not getattr(pdf_file, "filename", None):
        raise HTTPException(400, "Falta subir un PDF en el campo 'pdf_file'. Este endpoint requiere un archivo PDF.")

    if not pdf_file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "El archivo de PDF debe tener extensión .pdf")

    tmp_data_name = None
    tmp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    try:
        # Guardar PDF (siempre requerido)
        tmp_pdf.write(await pdf_file.read())
        tmp_pdf.close()

        # Si se proporcionó data_file, validar y guardarlo
        if data_file is not None:
            ext_data = os.path.splitext(data_file.filename)[1].lower()
            if ext_data not in (".json", ".txt"):
                raise HTTPException(400, "El archivo de datos debe ser .json o .txt")

            tmp_data = tempfile.NamedTemporaryFile(delete=False, suffix=ext_data)
            try:
                tmp_data.write(await data_file.read())
                tmp_data.close()
                tmp_data_name = tmp_data.name
            except:
                try: os.unlink(tmp_data.name)
                except: pass
                raise

        # Ejecutar comparación solo si se cargó data_file
        if tmp_data_name:
            result = comparar_valores_json_pdf(tmp_data_name, tmp_pdf.name)
            result.setdefault("comparison_performed", True)
        else:
            result = {"comparison_performed": False, "comparison_result": None}

        # Detectar personas con DNI o matrícula (siempre se ejecuta)
        personas_detectadas = detectar_personas_dni_matricula(tmp_pdf.name)
        result["personas_identificadas_pdf"] = personas_detectadas

    finally:
        # Limpiar temporales
        if tmp_data_name:
            try: os.unlink(tmp_data_name)
            except: pass
        try: os.unlink(tmp_pdf.name)
        except: pass

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