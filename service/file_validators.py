"""
Módulo de validación de archivos con múltiples capas de seguridad.
Valida extensiones, MIME types reportados por el cliente y contenido real del archivo.

Utiliza la librería 'filetype' para detectar el tipo real del archivo.
"""
import os
import json
import filetype
from fastapi import UploadFile, HTTPException


# MIME types permitidos para cada tipo de archivo
ALLOWED_MIME_TYPES = {
    'pdf': {
        'extensions': ['.pdf'],
        'mime_types': ['application/pdf'],
        'magic_bytes': b'%PDF'
    },
    'json': {
        'extensions': ['.json'],
        'mime_types': ['application/json', 'text/json'],
        'magic_bytes_check': lambda content: content.lstrip().startswith((b'{', b'['))
    },
    'txt': {
        'extensions': ['.txt'],
        'mime_types': ['text/plain'],
        'magic_bytes_check': lambda content: _is_valid_text(content)
    }
}


def _is_valid_text(content: bytes) -> bool:
    """
    Verifica si el contenido es texto plano válido (UTF-8).
    
    Args:
        content: Contenido del archivo en bytes
        
    Returns:
        True si es texto válido, False en caso contrario
    """
    try:
        content.decode('utf-8')
        return True
    except UnicodeDecodeError:
        return False


def validar_extension(filename: str) -> str:
    """
    Capa 1: Validación por extensión del archivo.
    
    Args:
        filename: Nombre del archivo con extensión
        
    Returns:
        Extensión del archivo en minúsculas (ej: '.pdf')
        
    Raises:
        HTTPException: Si la extensión no es permitida
    """
    ext = os.path.splitext(filename)[1].lower()
    
    # Obtener todas las extensiones permitidas
    allowed_extensions = []
    for file_type in ALLOWED_MIME_TYPES.values():
        allowed_extensions.extend(file_type['extensions'])
    
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Extensión '{ext}' no permitida. Solo se aceptan: {', '.join(allowed_extensions)}"
        )
    
    return ext


def validar_mime_cliente(file: UploadFile, expected_type: str) -> None:
    """
    Capa 2: Validación del MIME type reportado por el cliente.
    
    Args:
        file: Archivo subido
        expected_type: Tipo esperado ('pdf', 'json', 'txt')
        
    Raises:
        HTTPException: Si el MIME type del cliente no coincide con el esperado
    """
    if expected_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=500,
            detail=f"Tipo de archivo '{expected_type}' no configurado en el sistema"
        )
    
    allowed_mimes = ALLOWED_MIME_TYPES[expected_type]['mime_types']
    client_mime = file.content_type
    
    if not client_mime or client_mime.lower() not in allowed_mimes:
        raise HTTPException(
            status_code=400,
            detail=f"MIME type '{client_mime}' no válido para {expected_type.upper()}. "
                   f"Esperado: {', '.join(allowed_mimes)}"
        )


def validar_mime_real(content: bytes, filename: str, expected_type: str) -> str:
    """
    Capa 3: Validación del MIME type real usando filetype.
    Detecta el tipo real del archivo analizando su contenido.
    
    Args:
        content: Contenido del archivo en bytes
        filename: Nombre del archivo
        expected_type: Tipo esperado ('pdf', 'json', 'txt')
        
    Returns:
        MIME type real detectado
        
    Raises:
        HTTPException: Si el contenido no coincide con el tipo esperado
    """
    if expected_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=500,
            detail=f"Tipo de archivo '{expected_type}' no configurado en el sistema"
        )
    
    try:
        # Detectar tipo real del archivo con filetype
        kind = filetype.guess(content)
        
        if kind is None:
            # Si filetype no puede detectar, asumir texto plano si es decodificable
            if expected_type in ['json', 'txt'] and _is_valid_text(content):
                detected_mime = 'text/plain'
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"No se pudo detectar el tipo del archivo '{filename}'. "
                           f"Posible archivo corrupto o no reconocido."
                )
        else:
            detected_mime = kind.mime
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al detectar el tipo de archivo: {str(e)}"
        )
    
    allowed_mimes = ALLOWED_MIME_TYPES[expected_type]['mime_types']
    
    # Para PDF, ser estricto con el MIME type
    if expected_type == 'pdf':
        if detected_mime not in allowed_mimes:
            raise HTTPException(
                status_code=400,
                detail=f"El archivo '{filename}' fue detectado como '{detected_mime}' "
                       f"pero se esperaba {expected_type.upper()} ({', '.join(allowed_mimes)}). "
                       f"Posible archivo renombrado o falsificado."
            )
    # Para JSON y TXT, ser más flexible ya que filetype puede no detectarlos (son texto plano)
    elif expected_type in ['json', 'txt']:
        # Aceptar text/plain o si no se detectó nada (None) pero es texto válido
        if not (detected_mime in allowed_mimes or detected_mime.startswith('text/')):
            raise HTTPException(
                status_code=400,
                detail=f"El archivo '{filename}' fue detectado como '{detected_mime}' "
                       f"pero se esperaba {expected_type.upper()} (texto legible). "
                       f"Posible archivo binario, corrupto o falsificado."
            )
    
    return detected_mime


def validar_magic_bytes(content: bytes, filename: str, expected_type: str) -> None:
    """
    Capa 4: Validación adicional por magic bytes (firma del archivo).
    Verifica los primeros bytes del archivo para confirmar su tipo.
    
    Args:
        content: Contenido del archivo en bytes
        filename: Nombre del archivo
        expected_type: Tipo esperado ('pdf', 'json', 'txt')
        
    Raises:
        HTTPException: Si los magic bytes no coinciden con el tipo esperado
    """
    if expected_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=500,
            detail=f"Tipo de archivo '{expected_type}' no configurado en el sistema"
        )
    
    file_config = ALLOWED_MIME_TYPES[expected_type]
    
    # Verificar magic bytes si están definidos
    if 'magic_bytes' in file_config:
        magic_bytes = file_config['magic_bytes']
        if not content.startswith(magic_bytes):
            raise HTTPException(
                status_code=400,
                detail=f"El archivo '{filename}' no tiene la firma correcta de {expected_type.upper()}. "
                       f"Posible archivo corrupto o falsificado."
            )
    
    # Verificar mediante función personalizada si está definida
    elif 'magic_bytes_check' in file_config:
        check_function = file_config['magic_bytes_check']
        if not check_function(content):
            raise HTTPException(
                status_code=400,
                detail=f"El archivo '{filename}' no tiene un formato válido de {expected_type.upper()}. "
                       f"Posible archivo corrupto o falsificado."
            )


def _validar_contenido_json(content: bytes, filename: str) -> None:
    """
    Capa 5: Validación de contenido JSON (función interna).
    Verifica que el contenido sea un JSON válido parseándolo.
    
    Args:
        content: Contenido del archivo en bytes
        filename: Nombre del archivo
        
    Raises:
        HTTPException: Si el contenido no es JSON válido
    """
    try:
        # Intentar parsear como JSON
        json.loads(content.decode('utf-8'))
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=400,
            detail=f"El archivo '{filename}' no contiene JSON válido: {str(e)}"
        )
    except UnicodeDecodeError as e:
        raise HTTPException(
            status_code=400,
            detail=f"El archivo '{filename}' no tiene codificación UTF-8 válida: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error al validar el contenido JSON del archivo '{filename}': {str(e)}"
        )


async def validar_archivo_completo(
    file: UploadFile,
    expected_type: str,
    skip_mime_cliente: bool = False
) -> bytes:
    """
    Validación completa de un archivo en múltiples capas.
    
    Capas de validación:
    1. Extensión del archivo
    2. MIME type reportado por el cliente (opcional)
    3. MIME type real detectado con filetype
    4. Magic bytes / firma del archivo
    5. Contenido del archivo (para JSON)
    
    Args:
        file: Archivo subido
        expected_type: Tipo esperado ('pdf', 'json', 'txt')
        skip_mime_cliente: Si True, salta la validación del MIME del cliente
                          (útil cuando el cliente no envía content_type confiable)
        
    Returns:
        Contenido del archivo en bytes (ya leído)
        
    Raises:
        HTTPException: Si alguna validación falla
    """
    # Capa 1: Validar extensión
    validar_extension(file.filename)
    
    # Capa 2: Validar MIME reportado por el cliente (opcional)
    if not skip_mime_cliente:
        validar_mime_cliente(file, expected_type)
    
    # Leer contenido del archivo
    content = await file.read()
    
    if not content:
        raise HTTPException(
            status_code=400,
            detail=f"El archivo '{file.filename}' está vacío"
        )
    
    # Capa 3: Validar MIME real mediante análisis de contenido (filetype)
    validar_mime_real(content, file.filename, expected_type)
    
    # Capa 4: Validar magic bytes
    validar_magic_bytes(content, file.filename, expected_type)
    
    # Capa 5: Validar contenido (específico para JSON)
    if expected_type == 'json':
        _validar_contenido_json(content, file.filename)
    
    return content
