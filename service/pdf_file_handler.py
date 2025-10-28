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


def validar_archivo_pdf(pdf_file: UploadFile | None) -> None:
    """
    Valida que el archivo PDF esté presente y tenga extensión .pdf
    
    Args:
        pdf_file: Archivo PDF subido
        
    Raises:
        HTTPException: Si el archivo no es válido o no está presente
    """
    # Comprobación explícita cuando no se sube ningún archivo PDF
    if pdf_file is None or not getattr(pdf_file, "filename", None):
        raise HTTPException(
            status_code=400, 
            detail="Falta subir un PDF en el campo 'pdf_file'. Este endpoint requiere un archivo PDF."
        )

    if not pdf_file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400, 
            detail="El archivo de PDF debe tener extensión .pdf"
        )


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
    pdf_file: UploadFile,
    data_file: Optional[UploadFile] = None
) -> Tuple[str, Optional[str]]:
    """
    Guarda los archivos subidos en ubicaciones temporales.
    
    Args:
        pdf_file: Archivo PDF (requerido)
        data_file: Archivo de datos opcional (.json o .txt)
        
    Returns:
        Tupla con (ruta_pdf_temporal, ruta_data_temporal_o_None)
        
    Raises:
        HTTPException: Si hay errores al guardar los archivos
    """
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
                raise HTTPException(
                    status_code=400,
                    detail="El archivo de datos debe ser .json o .txt"
                )

            tmp_data = tempfile.NamedTemporaryFile(delete=False, suffix=ext_data)
            try:
                tmp_data.write(await data_file.read())
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
        
        return tmp_pdf.name, tmp_data_name
        
    except HTTPException:
        # Limpiar PDF temporal si hay error
        try:
            os.unlink(tmp_pdf.name)
        except:
            pass
        raise
    except Exception as e:
        # Limpiar PDF temporal si hay error inesperado
        try:
            os.unlink(tmp_pdf.name)
        except:
            pass
        raise HTTPException(
            status_code=500,
            detail=f"Error al guardar archivos: {str(e)}"
        )


def limpiar_archivos_temporales(tmp_pdf_path: str, tmp_data_path: Optional[str] = None) -> None:
    """
    Elimina los archivos temporales creados.
    
    Args:
        tmp_pdf_path: Ruta al archivo PDF temporal
        tmp_data_path: Ruta al archivo de datos temporal (opcional)
    """
    if tmp_data_path:
        try:
            os.unlink(tmp_data_path)
        except:
            pass
    
    try:
        os.unlink(tmp_pdf_path)
    except:
        pass


async def procesar_pdf_y_comparar(
    pdf_file: UploadFile,
    data_file: Optional[UploadFile] = None
) -> Dict[str, Any]:
    """
    Función principal que procesa el PDF y opcionalmente compara con datos externos.
    
    Flujo de procesamiento:
    1. Valida que el archivo PDF sea válido
    2. Guarda archivos temporales
    3. Verifica que el PDF no esté escaneado
    4. Detecta personas con DNI/matrícula en el PDF
    5. Si se proporcionó data_file, compara los datos
    6. Limpia archivos temporales
    
    Args:
        pdf_file: Archivo PDF a procesar
        data_file: Archivo de datos opcional para comparación (.json o .txt)
        
    Returns:
        Diccionario con los resultados del procesamiento:
        - comparison_performed: bool indicando si se realizó comparación
        - comparison_result: resultado de la comparación (si aplica)
        - personas_identificadas_pdf: lista de personas detectadas en el PDF
        
    Raises:
        HTTPException: Si hay errores en el procesamiento
    """
    # 1. Validar archivo PDF
    validar_archivo_pdf(pdf_file)
    
    tmp_pdf_path = None
    tmp_data_path = None
    
    try:
        # 2. Guardar archivos temporales
        tmp_pdf_path, tmp_data_path = await guardar_archivos_temporales(pdf_file, data_file)
        
        # 3. Verificar que el PDF no esté escaneado
        detectar_pdf_escaneado(tmp_pdf_path)
        
        # 4. Ejecutar comparación solo si se cargó data_file
        if tmp_data_path:
            result = comparar_valores_json_pdf(tmp_data_path, tmp_pdf_path)
            result.setdefault("comparison_performed", True)
        else:
            result = {
                "comparison_performed": False,
                "comparison_result": None
            }
        
        # 5. Detectar personas con DNI o matrícula (siempre se ejecuta)
        personas_detectadas = detectar_personas_dni_matricula(tmp_pdf_path)
        result["personas_identificadas_pdf"] = personas_detectadas
        
        return result
        
    finally:
        # 6. Limpiar archivos temporales
        if tmp_pdf_path or tmp_data_path:
            limpiar_archivos_temporales(tmp_pdf_path, tmp_data_path)
