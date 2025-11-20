"""
Constantes compartidas para detección y extracción de entidades.
Este archivo centraliza patrones regex, stop-words y configuraciones
para evitar duplicación de código.
"""
import re

# Patrones de documentos (regex base)
PATRONES_DOCUMENTOS = {
    "DNI": r'\bDNI\s+(\d+)\b',
    "MATRICULA": r'\bMATRICULA\s+(\d+)\b',
    "CUIF": r'\bCUIF\s+(\d+)\b',
    "CUIT": r'\bCUIT\s+(\d+)\b',
    "CUIL": r'\bCUIL\s+(\d+)\b',
}

# Stop-words para filtrar nombres
STOP_WORDS = {
    # Documentos / etiquetas
    "dni", "matricula", "mp", "cuif", "cuit", "cuil",
    
    # Tratamientos y títulos
    "señor", "señora", "sr", "sra", "srta", "juez", "jueza",
    "ciudadano", "ciudadana",
    "doctor", "doctora", "dr", "dra", "drs", "dras", "dr.", "dra.", "drs.", "dras.",
    "abogado", "abogada", "letrado", "letrada",
}

# Patrones de nombres (para reutilizar)
PATRON_NOMBRE_NATURAL = re.compile(
    r'\b([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ]+'
    r'(?:\s+[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ]+){1,5})\b'
)

PATRON_NOMBRE_JURIDICO = re.compile(
    r'\b('
    r'[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ\.\&]+'
    r'(?:\s+[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ\.\&]+){1,7}'
    r')\b'
)

# Anclas contextuales - Nombres a la DERECHA del ancla
ANCLAS_CONTEXTUALES_DERECHA = [
    # Tratamientos y títulos
    "sr", "sra", "dres", "dr", "dra", "doctoras","doctores","señor", "señora", 
    "doctor", "doctora", "abogado", "abogada",
    "apoderado", "patrocinio", "letrado", "letrada",
    "juez", "jueza", "ciudadano", "ciudadana", "banco",

    # Verbos y contextos legales que preceden nombres
    "identificado", "identificada", "comparece", "comparecen",
    "representado", "representada", "mandante", "actúa",
    "suscribe", "conjuntamente"
]

# Anclas contextuales - Nombres a la IZQUIERDA del ancla
ANCLAS_CONTEXTUALES_IZQUIERDA = [
    # Documentos de identidad (indican que el nombre está cerca)
    "dni", "cuil", "cuit", "cuif", "matricula", "matrícula"
]

# Unión de ambas listas para uso en limpieza (Fase 4)
ANCLAS_CONTEXTUALES = ANCLAS_CONTEXTUALES_DERECHA + ANCLAS_CONTEXTUALES_IZQUIERDA

# Palabras a eliminar del inicio/final de nombres (preposiciones, conjunciones)
PALABRAS_LIMPIEZA_BORDES = {"del", "de", "y", "e", "la", "el", "los", "las"}


def limpiar_bordes_nombre(nombre: str) -> str:
    """
    Elimina preposiciones y conjunciones del inicio y final de nombres.
    
    Esta función limpia palabras como "del", "de", "y" que pueden quedar
    pegadas al nombre durante la extracción por proximidad a anclas.
    
    Ejemplos:
        "Del Rene Antonio Quer" → "Rene Antonio Quer"
        "Y Bianca Giovanna Muller" → "Bianca Giovanna Muller"
        "Maria De Los Angeles Y" → "Maria De Los Angeles"
        "De La Rosa Martinez Del" → "La Rosa Martinez"
    
    Args:
        nombre: Nombre a limpiar
        
    Returns:
        Nombre limpio sin preposiciones/conjunciones en los bordes
    """
    if not nombre or not nombre.strip():
        return ""
    
    tokens = nombre.split()
    
    # Eliminar del inicio
    while tokens and tokens[0].lower() in PALABRAS_LIMPIEZA_BORDES:
        tokens.pop(0)
    
    # Eliminar del final
    while tokens and tokens[-1].lower() in PALABRAS_LIMPIEZA_BORDES:
        tokens.pop()
    
    return ' '.join(tokens).strip()


def _expandir_lemas(palabras_base):
    """
    Expande un conjunto de palabras agregando variantes comunes (género, número).
    Esto permite lematización sin necesidad de spaCy en tiempo de ejecución.
    
    Args:
        palabras_base: Set o lista de palabras base
        
    Returns:
        Set expandido con las palabras originales y sus variantes
    """
    expandidas = set()
    
    # Reglas de expansión comunes en español
    reglas_expansion = [
        # Singular -> Plural
        (r'([^s])$', r'\1s'),           # ley -> leyes, cargo -> cargos
        (r'([aeiou])$', r'\1s'),        # carta -> cartas
        (r'([íúó])n$', r'\1nes'),       # resolución -> resoluciones
        
        # Género (masculino <-> femenino)
        (r'o$', 'a'),                    # jurídico -> jurídica
        (r'a$', 'o'),                    # jurídica -> jurídico
        
        # Terminaciones comunes
        (r'([^aeiou])$', r'\1es'),      # provincial -> provinciales (opcional)
    ]
    
    for palabra in palabras_base:
        expandidas.add(palabra.lower())
        
        # Agregar plural agregando 's'
        if not palabra.endswith('s'):
            expandidas.add(palabra + 's')
        # Agregar singular quitando 's'
        elif palabra.endswith('s') and len(palabra) > 2:
            expandidas.add(palabra[:-1])
        
        # Cambios de género o/a
        if palabra.endswith('o'):
            expandidas.add(palabra[:-1] + 'a')
        elif palabra.endswith('a') and not palabra.endswith(('ia', 'ua')):
            expandidas.add(palabra[:-1] + 'o')
        
        # Casos especiales: ión/iones
        if palabra.endswith('ión'):
            expandidas.add(palabra[:-2] + 'ones')
        elif palabra.endswith('ones'):
            expandidas.add(palabra[:-4] + 'ión')
    
    return expandidas


# Palabras base para filtrado de nombres (se expandirán automáticamente)
_PALABRAS_FILTRO_BASE = {
    # Términos jurídicos/administrativos (solo formas base)
    "expediente", "orden", "jurídico",
    "estado", "provincial", "provincia", "nacional",
    "constitucional", "constitución", "ley", "administrativo",
    "sentencia", "consejo", "jubilación", "ordinario", "carta", "poder", "legislativo",
    "social", "seguridad", "federal", "derecho", "art", "resolución", "ente", 
    "cargo", "decreto", "nación", "judicial", "propiedad","juzgado", "firmado", "oficio",
    
    # Ubicaciones
    "calle", "avenida", "buenos", "aires", "corrientes", "argentina", 
    
    # Instituciones comunes
    "institución", "instituto", "ministerio", "secretaría", "dirección", "cámara",
    "corte", "supremo", "tribunal", "amparo",
    
    # Agregados específicos que no siguen reglas estándar
    "ctes",  # abreviatura
}

# Expandir automáticamente las palabras con sus variantes (género, número)
PALABRAS_FILTRO_NOMBRES = _expandir_lemas(_PALABRAS_FILTRO_BASE)