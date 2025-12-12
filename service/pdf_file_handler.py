"""
Módulo de Servicio para el manejo y validación de archivos PDF y datos.
Contiene funciones para:
- Validar archivos PDF
- Guardar archivos temporales
- Detectar si un PDF está escaneado
- Procesar la lógica completa de comparación y extracción
"""
import os
import tempfile
import fitz  # PyMuPDF
from typing import Tuple, Optional, Dict, Any
from fastapi import UploadFile, HTTPException

from funcs.comparar_json_pdf import comparar_valores_json_pdf
from funcs.detectar_personas_pdf import detectar_personas_dni_matricula
from funcs.detectar_identificadores_huerfanos import extraer_identificadores_huerfanos
from funcs.normalizacion.normalizar_y_extraer_texto_pdf import normalizacion_avanzada_pdf
from service.file_validators import validar_archivo_completo


def detectar_pdf_escaneado(path_pdf: str, umbral_texto: int = 100) -> bool:
    """
    Detecta si un PDF está compuesto principalmente por imágenes escaneadas (sin texto embebido).
    - Abre el PDF con PyMuPDF y cuenta la cantidad de caracteres de texto embebido.
    - Si la cantidad total es menor al umbral, se considera escaneado.
    
    Args:
        path_pdf: Ruta al archivo PDF
        umbral_texto: Número mínimo de caracteres para considerar que tiene texto embebido
        
    Returns:
        True si el PDF está escaneado (sin texto), False si contiene texto
        
    Raises:
        HTTPException: Si no se puede analizar el PDF o si está escaneado
    """
    try:
        with fitz.open(path_pdf) as doc:
            total_chars = sum(len(page.get_text("text") or "") for page in doc)

        if total_chars < umbral_texto:
            raise HTTPException(
                status_code=400,
                detail=f"El PDF '{os.path.basename(path_pdf)}' parece estar ESCANEADO (sin texto embebido). "
                       f"No se puede procesar este tipo de documentos. Por favor, proporcione un PDF con texto extraíble."
            )
        
        return False  # No está escaneado, contiene texto

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"No se pudo analizar el PDF: {str(e)}"
        )


async def guardar_archivos_temporales(
    pdf_file_main: Optional[UploadFile] = None,
    data_file: Optional[UploadFile] = None,
    txt_file_main: Optional[UploadFile] = None
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Guarda los archivos subidos en ubicaciones temporales después de validarlos.
    Aplica validación completa en múltiples capas (extensión, MIME cliente, MIME real, magic bytes).
    
    Args:
        pdf_file_main: Archivo PDF principal (opcional, mutuamente excluyente con txt_file_main)
        data_file: Archivo de datos opcional (.json o .txt)
        txt_file_main: Archivo TXT principal (opcional, mutuamente excluyente con pdf_file_main)
        
    Returns:
        Tupla con (ruta_pdf_temporal_o_None, ruta_data_temporal_o_None, ruta_txt_temporal_o_None)
        
    Raises:
        HTTPException: Si hay errores al guardar los archivos o las validaciones fallan
    """
    tmp_data_name = None
    tmp_pdf_name = None
    tmp_txt_name = None
    
    try:
        # Guardar PDF si se proporcionó
        if pdf_file_main is not None:
            tmp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            try:
                # Validar y leer PDF con todas las capas de seguridad
                pdf_content = await validar_archivo_completo(pdf_file_main, 'pdf')
                
                # Guardar PDF
                tmp_pdf.write(pdf_content)
                tmp_pdf.close()
                tmp_pdf_name = tmp_pdf.name
            except Exception as e:
                try:
                    os.unlink(tmp_pdf.name)
                except:
                    pass
                raise

        # Guardar TXT si se proporcionó
        if txt_file_main is not None:
            tmp_txt = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
            try:
                # Validar y leer TXT con todas las capas de seguridad
                txt_content = await validar_archivo_completo(txt_file_main, 'txt')
                
                # Guardar TXT
                tmp_txt.write(txt_content)
                tmp_txt.close()
                tmp_txt_name = tmp_txt.name
            except Exception as e:
                try:
                    os.unlink(tmp_txt.name)
                except:
                    pass
                raise

        # Si se proporcionó data_file, validar y guardarlo
        if data_file is not None:
            ext_data = os.path.splitext(data_file.filename)[1].lower()
            
            # Determinar el tipo esperado según la extensión
            if ext_data == '.json':
                expected_type = 'json'
            elif ext_data == '.txt':
                expected_type = 'txt'
            else:
                raise HTTPException(
                    status_code=400,
                    detail="El archivo de datos debe ser .json o .txt"
                )
            
            # Validar y leer archivo de datos con todas las capas de seguridad
            data_content = await validar_archivo_completo(data_file, expected_type)

            tmp_data = tempfile.NamedTemporaryFile(delete=False, suffix=ext_data)
            try:
                tmp_data.write(data_content)
                tmp_data.close()
                tmp_data_name = tmp_data.name
            except Exception as e:
                # Limpiar archivo temporal si falla
                try:
                    os.unlink(tmp_data.name)
                except:
                    pass
                raise HTTPException(
                    status_code=500,
                    detail=f"Error al guardar el archivo de datos: {str(e)}"
                )
        
        return tmp_pdf_name, tmp_data_name, tmp_txt_name
        
    except HTTPException:
        # Limpiar archivos temporales si hay error
        if tmp_pdf_name:
            try:
                os.unlink(tmp_pdf_name)
            except:
                pass
        if tmp_txt_name:
            try:
                os.unlink(tmp_txt_name)
            except:
                pass
        if tmp_data_name:
            try:
                os.unlink(tmp_data_name)
            except:
                pass
        raise
    except Exception as e:
        # Limpiar archivos temporales si hay error inesperado
        if tmp_pdf_name:
            try:
                os.unlink(tmp_pdf_name)
            except:
                pass
        if tmp_txt_name:
            try:
                os.unlink(tmp_txt_name)
            except:
                pass
        if tmp_data_name:
            try:
                os.unlink(tmp_data_name)
            except:
                pass
        raise HTTPException(
            status_code=500,
            detail=f"Error al guardar archivos: {str(e)}"
        )


def limpiar_archivos_temporales(tmp_pdf_path: Optional[str] = None, tmp_data_path: Optional[str] = None, tmp_txt_path: Optional[str] = None) -> None:
    """
    Elimina los archivos temporales creados.
    
    Args:
        tmp_pdf_path: Ruta al archivo PDF temporal (opcional)
        tmp_data_path: Ruta al archivo de datos temporal (opcional)
        tmp_txt_path: Ruta al archivo TXT temporal (opcional)
    """
    if tmp_data_path:
        try:
            os.unlink(tmp_data_path)
        except:
            pass
    
    if tmp_pdf_path:
        try:
            os.unlink(tmp_pdf_path)
        except:
            pass
    
    if tmp_txt_path:
        try:
            os.unlink(tmp_txt_path)
        except:
            pass


async def procesar_pdf_y_comparar(
    pdf_file_main: Optional[UploadFile] = None,
    data_file: Optional[UploadFile] = None,
    txt_file_main: Optional[UploadFile] = None
) -> Dict[str, Any]:
    """
    Función principal que procesa el PDF o TXT y opcionalmente compara con datos externos.
    
    Flujo de procesamiento:
    1. Valida presencia de PDF o TXT (mutuamente excluyentes)
    2. Guarda archivos temporales (con validación completa)
    3. Si es PDF: Verifica que no esté escaneado
    4. Detecta personas con DNI/matrícula en el PDF o TXT
    5. Detecta identificadores huérfanos (sin persona) e inválidos (CUIL/CUIT con dígito verificador incorrecto)
    6. Si se proporcionó data_file, compara los datos
    7. Limpia archivos temporales
    
    Args:
        pdf_file_main: Archivo PDF principal a procesar (opcional, mutuamente excluyente con txt_file_main)
        data_file: Archivo de datos opcional para comparación (.json o .txt)
        txt_file_main: Archivo TXT principal a procesar (opcional, mutuamente excluyente con pdf_file_main)
        
    Returns:
        Diccionario con los resultados del procesamiento:
        - comparison_performed: bool indicando si se realizó comparación
        - comparison_result: resultado de la comparación (si aplica)
        - personas_identificadas_pdf: lista de personas detectadas con sus identificadores
        - identificadores_huerfanos: DNI, CUIL, CUIT sin persona asociada
        - identificadores_invalidos: CUIL, CUIT con dígito verificador incorrecto
        
    Raises:
        HTTPException: Si hay errores en el procesamiento
    """
    tmp_pdf_path = None
    tmp_data_path = None
    tmp_txt_path = None
    
    try:
        # 1. Guardar archivos temporales (incluye validación completa)
        tmp_pdf_path, tmp_data_path, tmp_txt_path = await guardar_archivos_temporales(pdf_file_main, data_file, txt_file_main)
        
        # 2. Si es PDF, verificar que no esté escaneado
        if tmp_pdf_path:
            detectar_pdf_escaneado(tmp_pdf_path)
        
        # 3. Ejecutar comparación solo si se cargó data_file
        if tmp_data_path:
            # Usar el archivo de origen apropiado (PDF o TXT)
            source_file = tmp_pdf_path if tmp_pdf_path else tmp_txt_path
            result = comparar_valores_json_pdf(tmp_data_path, source_file)
            result.setdefault("comparison_performed", True)
        else:
            result = {
                "comparison_performed": False,
                "comparison_result": None
            }
        
        # 4. Detectar personas con DNI o matrícula (siempre se ejecuta)
        if tmp_pdf_path:
            personas_detectadas = detectar_personas_dni_matricula(path_pdf=tmp_pdf_path)
            # Obtener texto normalizado para búsqueda de huérfanos
            texto_normalizado = normalizacion_avanzada_pdf(path_pdf=tmp_pdf_path)
        else:
            # Leer el contenido del archivo TXT
            with open(tmp_txt_path, 'r', encoding='utf-8') as f:
                txt_content = f.read()
            personas_detectadas = detectar_personas_dni_matricula(raw_text=txt_content)
            # Obtener texto normalizado para búsqueda de huérfanos
            texto_normalizado = normalizacion_avanzada_pdf(raw_text=txt_content)
        
        result["personas_identificadas_pdf"] = personas_detectadas
        
        # 5. Detectar identificadores huérfanos e inválidos (nueva funcionalidad)
        identificadores_extra = extraer_identificadores_huerfanos(
            texto=texto_normalizado,
            personas_identificadas=personas_detectadas
        )
        
        # Agregar identificadores huérfanos e inválidos al resultado
        result["identificadores_huerfanos"] = identificadores_extra["identificadores_huerfanos"]
        result["identificadores_invalidos"] = identificadores_extra["identificadores_invalidos"]
        
        return result
        
    finally:
        # 6. Limpiar archivos temporales
        limpiar_archivos_temporales(tmp_pdf_path, tmp_data_path, tmp_txt_path)
