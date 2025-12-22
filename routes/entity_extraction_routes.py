"""
Router de FastAPI para extracción de entidades específicas de documentos PDF.
Permite al usuario seleccionar qué entidades desea extraer (nombres, DNI, matrícula, CUIF, CUIT, CUIL).
"""
from fastapi import APIRouter, UploadFile, File, Body
from fastapi.responses import JSONResponse
from typing import List, Optional

from service.entity_extraction_service import (
    procesar_extraccion_desde_pdf,
    procesar_extraccion_desde_texto
)

#---------------------------------------------------------- Router
router = APIRouter(tags=["Extractor de Entidades Específicas"])

# ---------------------------------------------------------- Post
@router.post("/extract_entities_from_pdf", summary="Extrae entidades específicas de un PDF",
    description=(
        "Analiza un archivo PDF y extrae únicamente las entidades solicitadas por el usuario. "
        "Entidades disponibles: nombre, dni, matricula, cuif, cuit, cuil y cbu."
        "Puedes solicitar una o múltiples entidades."
    )
)
async def extract_entities_from_pdf(
    pdf_file: UploadFile = File(..., description="Archivo PDF a analizar"),
    entities: List[str] = Body(
        ..., 
        description="Lista de entidades a extraer (ej: nombre, dni, cuit, cuil, cuif, cbu)",
        example="nombre, dni"
    )
):
    """
    Extrae entidades específicas de un PDF según lo solicitado por el usuario.
    
    Args:
        pdf_file: Archivo PDF a analizar
        entities: Lista de entidades a extraer. Valores permitidos:
            - "nombre" o "nombres": Nombres de personas (naturales y jurídicas)
            - "dni": Números de DNI
            - "matricula": Números de matrícula profesional
            - "cuif": Números de CUIF
            - "cuit": Números de CUIT
            - "cuil": Números de CUIL
            - "cbu": Clave Bancaria Uniforme
    """
    response = await procesar_extraccion_desde_pdf(pdf_file, entities)
    return JSONResponse(content=response, status_code=200)


# ---------------------------------------------------------- Post
@router.post("/extract_entities_from_text", summary="Extrae entidades específicas desde texto plano o archivo",
    description=(
        "Analiza texto plano o un archivo .txt/.json y extrae únicamente las entidades solicitadas. "
        "Entidades disponibles: nombre, dni, matricula, cuif, cuit, cuil, cbu. "
        "Puedes proporcionar el texto directamente o subir un archivo, pero NO ambos a la vez. "
        "Si solicitas CUIL o CUIT, también se validarán automáticamente los dígitos verificadores "
        "y se reportarán los identificadores inválidos."
    )
)
async def extract_entities_from_text(
    text_file: Optional[UploadFile] = File(None, description="Archivo .txt o .json con el texto a analizar"),
    raw_text: Optional[str] = Body(None, description="Texto plano a analizar (alternativa al archivo)"),
    entities: List[str] = Body(
        ..., 
        description="Lista de entidades a extraer (ej: nombre, dni, cuit, cuil, cuif, cbu)",
        example="nombre, dni"
    )
):
    """
    Extrae entidades específicas desde texto plano o archivo según lo solicitado.
    
    Si se solicitan CUIL o CUIT, también se validarán automáticamente los dígitos 
    verificadores y se incluirá un campo adicional 'identificadores_invalidos' en 
    la respuesta con los CUIL/CUIT que tengan errores.
    
    Args:
        text_file: Archivo .txt o .json con el texto (opcional)
        raw_text: Texto plano directo (opcional)
        entities: Lista de entidades a extraer. Valores permitidos:
            - "nombre" o "nombres": Nombres de personas (naturales y jurídicas)
            - "dni": Números de DNI
            - "matricula": Números de matrícula profesional
            - "cuif": Números de CUIF
            - "cuit": Números de CUIT
            - "cuil": Números de CUIL
            - "cbu": Clave Bancaria Uniforme
    """
    response = await procesar_extraccion_desde_texto(text_file, raw_text, entities)
    return JSONResponse(content=response, status_code=200)
