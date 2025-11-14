"""
Router de FastAPI para extracción de entidades específicas de documentos PDF.
Permite al usuario seleccionar qué entidades desea extraer (nombres, DNI, matrícula, CUIF, CUIT, CUIL).
"""
import tempfile
import os

from fastapi import APIRouter, UploadFile, File, HTTPException, Body
from fastapi.responses import JSONResponse
from typing import List, Dict, Optional
from service.file_validators import validar_archivo_completo
from service.pdf_file_handler import detectar_pdf_escaneado

# Usar spaCy
from funcs.nlp_extractors.extraer_entidades_especificas_spacy import ( extraer_entidades_especificas, validar_entidades_solicitadas)

#---------------------------------------------------------- Router
router = APIRouter(tags=["Extractor de Entidades Específicas"])

# ---------------------------------------------------------- Post - 
@router.post("/extract_entities_from_pdf", summary="Extrae entidades específicas de un PDF",
    description=(
        "Analiza un archivo PDF y extrae únicamente las entidades solicitadas por el usuario. "
        "Entidades disponibles: nombre, dni, matricula, cuif, cuit, cuil. "
        "Puedes solicitar una o múltiples entidades."
    )
)
async def extract_entities_from_pdf(
    pdf_file: UploadFile = File(..., description="Archivo PDF a analizar"),
    entities: List[str] = Body(
        ..., 
        description="Lista de entidades a extraer (ej: ['nombre', 'dni', 'cuit'])",
        example=["nombre", "dni"]
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
    
    Returns:
        JSON con las entidades encontradas organizadas por tipo
    
    Raises:
        HTTPException 400: Si el archivo no es válido o las entidades solicitadas son incorrectas
        HTTPException 500: Si hay un error interno al procesar el PDF
    """
    # Validar que el archivo sea un PDF real
    if not pdf_file:
        raise HTTPException(status_code=400, detail="No se proporcionó ningún archivo PDF")
    
    # Validar entidades solicitadas
    es_valido, mensaje_error = validar_entidades_solicitadas(entities)
    if not es_valido:
        raise HTTPException(status_code=400, detail=mensaje_error)
    
    tmp_pdf = None
    
    try:
        # Validar archivo PDF con todas las capas de seguridad
        pdf_content = await validar_archivo_completo(pdf_file, 'pdf')
        
        # Guardar temporalmente
        tmp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp_pdf.write(pdf_content)
        tmp_pdf.close()
        
        # Verificar que no esté escaneado
        detectar_pdf_escaneado(tmp_pdf.name)

        # Extraer entidades solicitadas
        # La visualización se controla desde funcs.nlp_extractors.visualization_displacy
        # modificando VISUALIZACION_HABILITADA y GUARDADO_HABILITADO
        resultado = extraer_entidades_especificas(
            entidades_solicitadas=entities,
            path_pdf=tmp_pdf.name
        )
        
        # Agregar metadatos
        response = {
            "archivo": pdf_file.filename,
            "entidades_solicitadas": entities,
            "resultados": resultado,
        }

        # Incluir información de visualización guardada si existe
        vis_info = None
        if isinstance(resultado, dict):
            vis = resultado.get('_visualization')
            if vis and isinstance(vis, dict):
                saved = vis.get('saved')
                if saved:
                    # saved contiene 'path', 'filename', 'url_file' y opcional 'svg_base64'
                    vis_info = {
                        'path': saved.get('path'),
                        'filename': saved.get('filename'),
                        'file_url': saved.get('url_file'),
                    }
                    if 'svg_base64' in saved:
                        vis_info['svg_base64'] = saved.get('svg_base64')
        if vis_info:
            response['visualization'] = vis_info

        # Resumen: contar solo listas de entidades (ignorar keys no-lista como _visualization)
        resumen = {}
        for tipo, items in resultado.items():
            if isinstance(items, list):
                resumen[tipo] = len(items)
        response['resumen'] = resumen
        
        return JSONResponse(content=response, status_code=200)
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al procesar el PDF: {str(e)}"
        )
    finally:
        # Limpieza de archivo temporal
        if tmp_pdf and os.path.exists(tmp_pdf.name):
            try:
                os.unlink(tmp_pdf.name)
            except Exception:
                pass
