"""
Módulo para detectar identificadores (DNI, CUIL, CUIT) que no están asociados a personas.
También valida si CUIL/CUIT tienen dígito verificador correcto.
"""
import re
from typing import Dict, List, Any, Set
from funcs.nlp_extractors.validadores_entidades import validar_dni, validar_cuil, validar_cuit


def extraer_identificadores_huerfanos(
    texto: str,
    personas_identificadas: List[str]
) -> Dict[str, Any]:
    """
    Extrae identificadores (DNI, CUIL, CUIT) del texto que NO están asociados a personas.
    También identifica CUIL/CUIT con dígito verificador incorrecto.
    
    Args:
        texto: Texto normalizado donde buscar
        personas_identificadas: Lista de strings con formato "Nombre | DNI N° 123 | CUIL N° 456"
        
    Returns:
        Diccionario con:
        - identificadores_huerfanos: DNI, CUIL, CUIT sin persona asociada
        - identificadores_invalidos: CUIL, CUIT con dígito verificador incorrecto
            Cada identificador inválido incluye:
            - numero: El número del identificador
            - contexto: Texto alrededor
            - valido: False (por definición)
            - razon: "Dígito verificador incorrecto"
            - tiene_dueno: True si está asociado a una persona, False si es huérfano
            - nombre_dueno: Nombre de la persona (si tiene_dueno=True) o None
            - observacion: "Asociado a: Nombre" o "Huérfano - no tiene persona asociada"
    """
    # 1. Extraer todos los identificadores asociados a personas
    identificadores_con_persona = _extraer_identificadores_asociados(personas_identificadas)
    
    # 2. Buscar todos los DNI, CUIL, CUIT en el texto
    todos_dni = _buscar_dni_en_texto(texto)
    todos_cuil = _buscar_cuil_en_texto(texto)
    todos_cuit = _buscar_cuit_en_texto(texto)
    
    # 3. Filtrar huérfanos (que NO están en identificadores_con_persona)
    dni_huerfanos = [
        doc for doc in todos_dni 
        if doc['numero'] not in identificadores_con_persona['dni']
    ]
    
    cuil_huerfanos = [
        doc for doc in todos_cuil 
        if doc['numero'] not in identificadores_con_persona['cuil']
    ]
    
    cuit_huerfanos = [
        doc for doc in todos_cuit 
        if doc['numero'] not in identificadores_con_persona['cuit']
    ]
    
    # 4. Identificar CUIL/CUIT inválidos (todos, incluso los que tienen persona)
    # Además, indicar si tiene dueño o es huérfano
    cuil_invalidos = []
    for doc in todos_cuil:
        if not doc['valido']:
            tiene_dueno = doc['numero'] in identificadores_con_persona['cuil']
            nombre_dueno = _buscar_nombre_dueno(personas_identificadas, 'CUIL', doc['numero']) if tiene_dueno else None
            
            cuil_invalidos.append({
                'numero': doc['numero'],
                'contexto': doc['contexto'],
                'razon': 'Dígito verificador incorrecto',
                'nombre_dueno': nombre_dueno
            })
    
    cuit_invalidos = []
    for doc in todos_cuit:
        if not doc['valido']:
            tiene_dueno = doc['numero'] in identificadores_con_persona['cuit']
            nombre_dueno = _buscar_nombre_dueno(personas_identificadas, 'CUIT', doc['numero']) if tiene_dueno else None
            
            cuit_invalidos.append({
                'numero': doc['numero'],
                'contexto': doc['contexto'],
                'razon': 'Dígito verificador incorrecto',
                'nombre_dueno': nombre_dueno
            })
    
    return {
        'identificadores_huerfanos': {
            'dni': dni_huerfanos,
            'cuil': cuil_huerfanos,
            'cuit': cuit_huerfanos
        },
        'identificadores_invalidos': {
            'cuil': cuil_invalidos,
            'cuit': cuit_invalidos
        }
    }


def validar_cuil_cuit_en_texto(texto: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Valida todos los CUIL y CUIT en el texto y retorna solo los inválidos.
    
    Esta función es independiente y no requiere personas identificadas.
    Útil para endpoints que solo necesitan detectar identificadores con errores.
    
    Args:
        texto: Texto normalizado donde buscar
        
    Returns:
        Diccionario con:
        - cuil: Lista de CUIL con dígito verificador incorrecto
        - cuit: Lista de CUIT con dígito verificador incorrecto
        
        Cada identificador incluye:
        - numero: El número del identificador
        - contexto: Texto alrededor
        - razon: "Dígito verificador incorrecto"
    """
    # Buscar todos los CUIL y CUIT en el texto
    todos_cuil = _buscar_cuil_en_texto(texto)
    todos_cuit = _buscar_cuit_en_texto(texto)
    
    # Filtrar solo los inválidos
    cuil_invalidos = [
        {
            'numero': doc['numero'],
            'contexto': doc['contexto'],
            'razon': 'Dígito verificador incorrecto'
        }
        for doc in todos_cuil
        if not doc['valido']
    ]
    
    cuit_invalidos = [
        {
            'numero': doc['numero'],
            'contexto': doc['contexto'],
            'razon': 'Dígito verificador incorrecto'
        }
        for doc in todos_cuit
        if not doc['valido']
    ]
    
    return {
        'cuil': cuil_invalidos,
        'cuit': cuit_invalidos
    }


def _extraer_identificadores_asociados(personas: List[str]) -> Dict[str, Set[str]]:
    """
    Extrae todos los números de identificadores que YA están asociados a personas.
    
    Args:
        personas: Lista de strings con formato "Nombre | DNI N° 123 | CUIL N° 456"
        
    Returns:
        Diccionario con sets de números por tipo: {'dni': {...}, 'cuil': {...}, 'cuit': {...}}
    """
    identificadores = {
        'dni': set(),
        'cuil': set(),
        'cuit': set(),
        'cuif': set(),
        'matricula': set()
    }
    
    for persona_str in personas:
        # Formato: "Juan Pérez | DNI N° 12345678 | CUIL N° 20123456789"
        # Dividir por "|" para obtener cada parte
        partes = persona_str.split('|')
        
        # Procesar cada parte (excepto la primera que es el nombre)
        for parte in partes[1:]:
            # Buscar patrón: "TIPO N° NUMERO"
            match = re.search(r'(DNI|CUIL|CUIT|CUIF|MATRICULA)\s+N°\s+(\d+)', parte, re.IGNORECASE)
            if match:
                tipo = match.group(1).lower()
                numero = match.group(2)
                
                if tipo in identificadores:
                    # Limpiar el número (quitar guiones, puntos, espacios)
                    numero_limpio = re.sub(r'[^\d]', '', numero)
                    identificadores[tipo].add(numero_limpio)
    
    return identificadores


def _buscar_nombre_dueno(personas: List[str], tipo_doc: str, numero_doc: str) -> str:
    """
    Busca el nombre de la persona asociada a un identificador específico.
    
    Args:
        personas: Lista de strings con formato "Nombre | DNI N° 123 | CUIL N° 456"
        tipo_doc: Tipo de documento ("DNI", "CUIL", "CUIT", etc.)
        numero_doc: Número del documento a buscar
        
    Returns:
        Nombre de la persona o None si no se encuentra
    """
    numero_limpio = re.sub(r'[^\d]', '', numero_doc)
    
    for persona_str in personas:
        # "Juan Pérez | DNI N° 12345678 | CUIL N° 20123456789"
        partes = persona_str.split('|')
        nombre = partes[0].strip()
        
        # Buscar en los documentos de esta persona
        for parte in partes[1:]:
            match = re.search(r'(DNI|CUIL|CUIT|CUIF|MATRICULA)\s+N°\s+(\d+)', parte, re.IGNORECASE)
            if match:
                tipo_encontrado = match.group(1).upper()
                numero_encontrado = re.sub(r'[^\d]', '', match.group(2))
                
                if tipo_encontrado == tipo_doc.upper() and numero_encontrado == numero_limpio:
                    return nombre
    
    return None


def _buscar_dni_en_texto(texto: str) -> List[Dict[str, Any]]:
    """
    Busca todos los DNI en el texto y los valida.
    
    Args:
        texto: Texto normalizado
        
    Returns:
        Lista de DNI encontrados con contexto y validez
    """
    patron = r'\bDNI\s+(\d{7,8})\b'
    regex = re.compile(patron, flags=re.IGNORECASE)
    
    resultados = []
    numeros_vistos = set()
    
    for match in regex.finditer(texto):
        numero = match.group(1)
        
        # Evitar duplicados
        if numero in numeros_vistos:
            continue
        numeros_vistos.add(numero)
        
        # Validar DNI
        valido = validar_dni(numero)
        
        # Extraer contexto
        contexto = _extraer_contexto(texto, match.start(), match.end())
        
        resultados.append({
            'numero': numero,
            'contexto': contexto,
            'valido': valido
        })
    
    return resultados


def _buscar_cuil_en_texto(texto: str) -> List[Dict[str, Any]]:
    """
    Busca todos los CUIL en el texto y los valida (incluido dígito verificador).
    
    Args:
        texto: Texto normalizado
        
    Returns:
        Lista de CUIL encontrados con contexto y validez
    """
    # Patrón flexible: acepta con o sin separadores, con o sin espacios
    patron = r'\bCUIL\s+(\d{2}[-\s]?\d{8}[-\s]?\d{1})\b'
    regex = re.compile(patron, flags=re.IGNORECASE)
    
    resultados = []
    numeros_vistos = set()
    
    for match in regex.finditer(texto):
        numero_raw = match.group(1)
        # Limpiar separadores
        numero = re.sub(r'[^\d]', '', numero_raw)
        
        # Validar que tenga 11 dígitos
        if len(numero) != 11:
            continue
        
        # Evitar duplicados
        if numero in numeros_vistos:
            continue
        numeros_vistos.add(numero)
        
        # Validar CUIL (incluye validación de dígito verificador)
        valido = validar_cuil(numero)
        
        # Extraer contexto
        contexto = _extraer_contexto(texto, match.start(), match.end())
        
        resultados.append({
            'numero': numero,
            'contexto': contexto,
            'valido': valido
        })
    
    return resultados


def _buscar_cuit_en_texto(texto: str) -> List[Dict[str, Any]]:
    """
    Busca todos los CUIT en el texto y los valida (incluido dígito verificador).
    
    Args:
        texto: Texto normalizado
        
    Returns:
        Lista de CUIT encontrados con contexto y validez
    """
    # Patrón flexible: acepta con o sin separadores, con o sin espacios
    # Ejemplos: "CUIT 30-12345678-9", "CUIT 30123456789", "CUIT 30 12345678 9"
    patron = r'\bCUIT\s+(\d{2}[-\s]?\d{8}[-\s]?\d{1})\b'
    regex = re.compile(patron, flags=re.IGNORECASE)
    
    resultados = []
    numeros_vistos = set()
    
    for match in regex.finditer(texto):
        numero_raw = match.group(1)
        # Limpiar separadores
        numero = re.sub(r'[^\d]', '', numero_raw)
        
        # Validar que tenga 11 dígitos
        if len(numero) != 11:
            continue
        
        # Evitar duplicados
        if numero in numeros_vistos:
            continue
        numeros_vistos.add(numero)
        
        # Validar CUIT (incluye validación de dígito verificador)
        valido = validar_cuit(numero)
        
        # Extraer contexto
        contexto = _extraer_contexto(texto, match.start(), match.end())
        
        resultados.append({
            'numero': numero,
            'contexto': contexto,
            'valido': valido
        })
    
    return resultados


def _extraer_contexto(texto: str, start: int, end: int, window: int = 60) -> str:
    """
    Extrae el contexto alrededor de una posición en el texto.
    
    Args:
        texto: Texto completo
        start: Posición inicial
        end: Posición final
        window: Ventana de contexto (caracteres antes y después)
        
    Returns:
        Contexto extraído
    """
    start_ctx = max(0, start - window)
    end_ctx = min(len(texto), end + window)
    return texto[start_ctx:end_ctx].strip()
