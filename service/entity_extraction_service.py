"""
Servicio para extraer entidades específicas de diferentes fuentes (PDF, texto, archivos).
Centraliza la lógica de negocio para mantener los endpoints limpios.
"""
import tempfile
import os
import json
from typing import List, Dict, Optional, Tuple
from fastapi import UploadFile, HTTPException

from service.file_validators import validar_archivo_completo
from service.pdf_file_handler import detectar_pdf_escaneado
from service.entity_parser import parse_entities_input
from funcs.nlp_extractors.extraer_entidades_especificas_spacy import (
    extraer_entidades_especificas,
    validar_entidades_solicitadas
)
from funcs.detectar_identificadores_huerfanos import validar_cuil_cuit_en_texto
from funcs.normalizacion.normalizar_y_extraer_texto_pdf import normalizacion_avanzada_pdf


async def procesar_extraccion_desde_pdf(
    pdf_file: UploadFile,
    entities: List[str]
) -> Dict:
    """
    Procesa la extracción de entidades desde un archivo PDF.
    
    Args:
        pdf_file: Archivo PDF a analizar
        entities: Lista de entidades a extraer (puede venir en múltiples formatos)
        
    Returns:
        Diccionario con resultados estructurados
        
    Raises:
        HTTPException: Si hay errores de validación o procesamiento
    """
    # Validar que el archivo sea un PDF real
    if not pdf_file:
        raise HTTPException(status_code=400, detail="No se proporcionó ningún archivo PDF")
    
    # Normalizar la entrada entities
    entities = parse_entities_input(entities)
    
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
        resultado = extraer_entidades_especificas(
            entidades_solicitadas=entities,
            path_pdf=tmp_pdf.name
        )
        
        # Construir respuesta estructurada
        return _construir_respuesta(
            fuente=pdf_file.filename,
            entities=entities,
            resultado=resultado
        )
        
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


async def procesar_extraccion_desde_texto(
    text_file: Optional[UploadFile],
    raw_text: Optional[str],
    entities: List[str]
) -> Dict:
    """
    Procesa la extracción de entidades desde texto plano o archivo .txt/.json.
    
    Args:
        text_file: Archivo .txt o .json (opcional)
        raw_text: Texto plano directo (opcional)
        entities: Lista de entidades a extraer (puede venir en múltiples formatos)
        
    Returns:
        Diccionario con resultados estructurados
        
    Raises:
        HTTPException: Si hay errores de validación o procesamiento
    """
    # Validar que se proporcione exactamente UNA fuente de texto
    if text_file and raw_text:
        raise HTTPException(
            status_code=400, 
            detail="Proporciona SOLO un archivo O texto plano, no ambos"
        )
    
    if not text_file and not raw_text:
        raise HTTPException(
            status_code=400,
            detail="Debes proporcionar un archivo de texto o texto plano"
        )
    
    # Normalizar la entrada entities
    entities = parse_entities_input(entities)
    
    # Validar entidades solicitadas
    es_valido, mensaje_error = validar_entidades_solicitadas(entities)
    if not es_valido:
        raise HTTPException(status_code=400, detail=mensaje_error)
    
    try:
        # Extraer texto según la fuente
        texto_a_analizar, nombre_fuente = await _extraer_texto_de_fuente(text_file, raw_text)
        
        # Validar que haya contenido
        if not texto_a_analizar or len(texto_a_analizar.strip()) == 0:
            raise HTTPException(
                status_code=400,
                detail="El texto proporcionado está vacío"
            )
        
        # Extraer entidades
        resultado = extraer_entidades_especificas(
            entidades_solicitadas=entities,
            path_pdf=None,
            raw_text=texto_a_analizar
        )
        
        # Validar identificadores inválidos si se solicitan CUIL o CUIT
        identificadores_invalidos = None
        if 'cuil' in entities or 'cuit' in entities:
            # Obtener texto normalizado para búsqueda de inválidos
            texto_normalizado = normalizacion_avanzada_pdf(raw_text=texto_a_analizar)
            identificadores_invalidos = validar_cuil_cuit_en_texto(texto_normalizado)
        
        # Construir respuesta estructurada
        return _construir_respuesta(
            fuente=nombre_fuente,
            entities=entities,
            resultado=resultado,
            identificadores_invalidos=identificadores_invalidos
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al procesar el texto: {str(e)}"
        )


async def _extraer_texto_de_fuente(
    text_file: Optional[UploadFile],
    raw_text: Optional[str]
) -> Tuple[str, str]:
    """
    Extrae texto desde archivo o texto plano.
    
    Args:
        text_file: Archivo .txt o .json (opcional)
        raw_text: Texto plano directo (opcional)
        
    Returns:
        Tupla (texto_extraido, nombre_fuente)
        
    Raises:
        HTTPException: Si hay errores de validación
    """
    # Caso 1: Archivo .txt o .json
    if text_file:
        # Validar extensión del archivo
        extension = text_file.filename.split('.')[-1].lower()
        if extension not in ['txt', 'json']:
            raise HTTPException(
                status_code=400,
                detail="Solo se permiten archivos .txt o .json"
            )
        
        # Validar archivo con todas las capas de seguridad
        content = await validar_archivo_completo(text_file, extension)
        
        # Extraer texto según el tipo de archivo
        texto_a_analizar = content.decode('utf-8')
        
        # Si es JSON, extraer todo el contenido como texto
        if extension == 'json':
            try:
                data = json.loads(texto_a_analizar)
                # Convertir el JSON completo a string para análisis
                texto_a_analizar = json.dumps(data, ensure_ascii=False, indent=2)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail="El archivo JSON no es válido"
                )
        
        return texto_a_analizar, text_file.filename
    
    # Caso 2: Texto plano directo
    else:
        return raw_text.strip(), "texto_directo"


def _construir_respuesta(
    fuente: str,
    entities: List[str],
    resultado: Dict,
    identificadores_invalidos: Optional[Dict] = None
) -> Dict:
    """
    Construye la respuesta estructurada con metadatos y resumen.
    
    Args:
        fuente: Nombre del archivo o fuente del texto
        entities: Lista de entidades solicitadas
        resultado: Resultado de la extracción
        identificadores_invalidos: Diccionario con CUIL/CUIT inválidos (opcional)
        
    Returns:
        Diccionario con respuesta estructurada
    """
    response = {
        "fuente": fuente,
        "entidades_solicitadas": entities,
        "resultados": resultado,
    }
    
    # Agregar identificadores inválidos si existen
    if identificadores_invalidos:
        response['identificadores_invalidos'] = identificadores_invalidos
    
    # Resumen: contar solo listas de entidades
    resumen = {}
    for tipo, items in resultado.items():
        if isinstance(items, list):
            resumen[tipo] = len(items)
    response['resumen'] = resumen
    
    return response
