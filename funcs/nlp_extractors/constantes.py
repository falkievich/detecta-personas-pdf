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

# Anclas contextuales para nombres
ANCLAS_CONTEXTUALES = [
    # Tratamientos y títulos
    "sr", "sra", "dr", "dra", "señor", "señora", 
    "doctor", "doctora", "abogado", "abogada",
    "apoderado", "patrocinio", "letrado", "letrada",
    
    # Documentos de identidad (indican que el nombre está cerca)
    "dni", "cuil", "cuit", "cuif", "matricula", "matrícula",
    
    # Verbos y contextos legales que preceden nombres
    "identificado", "identificada", "comparece", "comparecen",
    "representado", "representada", "mandante", "actúa",
    "suscribe", "conjuntamente"
]
