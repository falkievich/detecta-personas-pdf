"""
Abre un archivo PDF, extrae todo su texto concatenado y luego lo normaliza al eliminar saltos de línea, convertirlos en espacios y colapsar múltiples espacios consecutivos, devolviendo una sola línea de texto limpia.
"""
import fitz  # PyMuPDF se usa en vez de PyPDF2 para extraer texto de PDF
import re, unicodedata


def extraer_texto_crudo_pdf(path_pdf: str) -> str:
    """
    Extrae texto crudo del PDF SIN normalización agresiva.
    Preserva acentos, mayúsculas, puntuación y estructura original.
    Uso: Para spaCy NER (detección de entidades PERSON).
    
    Solo aplica limpieza mínima:
    - Convierte saltos de línea a espacios
    - Colapsa espacios múltiples
    - Normaliza Unicode (NFKC) para caracteres especiales
    
    NO realiza:
    - Reemplazos de etiquetas (Documento → DNI)
    - Eliminación de puntos/comas
    - Modificación de estructura del texto
    """
    texto = ''
    with fitz.open(path_pdf) as doc:
        for pagina in doc:
            texto += pagina.get_text()
    
    # Normalización Unicode ligera (solo para caracteres especiales)
    try:
        texto = unicodedata.normalize("NFKC", texto)
    except Exception:
        pass
    
    # Convertir saltos de línea a espacios (mínimo necesario)
    texto = texto.replace('\n', ' ').replace('\r', ' ')
    
    # Colapsar espacios múltiples
    texto = re.sub(r'\s+', ' ', texto).strip()
    
    return texto


# Extración de texto de un PDF + normalización simple
def normalizacion_simple_pdf(path_pdf='ley.pdf'):
    texto = ''
    with fitz.open(path_pdf) as doc:
        for pagina in doc:
            texto += pagina.get_text()

    # --- Normalización de símbolos de viñetas (solo símbolos) ---
    # Homogeneiza formas Unicode para capturar bullets "raros" provenientes de Word/PDF
    try:
        texto = unicodedata.normalize("NFKC", texto)
    except Exception:
        pass

    # Elimina marcadores de lista cuando aparecen como bullets (al inicio o tras un espacio)
    BULLETS_REGEX = r'(?:(?<=^)|(?<=\s))[\-\*\u2022\u2023\u25E6\u2043\u2219\u25AA\u25CF\u25CB\u25A0\u00B7\u204C\u204D\uF0B7\uF0A7\uF076](?=\s)'
    texto = re.sub(BULLETS_REGEX, ' ', texto)
    # --- fin normalización de símbolos ---

    # Normalizar el texto: eliminar saltos de línea y espacios múltiples
    texto = texto.replace('\n', ' ').replace('\r', ' ')
    texto = re.sub(r'\s+', ' ', texto).strip()

    return texto

def eliminar_puntos_antes_de_cuit(texto: str) -> str:
    """
    Elimina los puntos que estén entre caracteres alfanuméricos en las
    dos palabras inmediatamente anteriores a la palabra 'CUIT',
    respetando cualquier coma o espacio que las separe del resto.
    """
    # Captura dos "palabras" antes de ", CUIT"
    patrón = re.compile(
        r'(\b[\w\.]+)\s+([\w\.]+)(?=\s*,\s*CUIT\b)',
        flags=re.IGNORECASE
    )

    def _repl(match: re.Match) -> str:
        w1, w2 = match.group(1), match.group(2)
        # Solo quitamos puntos que estén entre letras/dígitos
        w1_clean = re.sub(r'(?<=\w)\.(?=\w)', '', w1)
        w2_clean = re.sub(r'(?<=\w)\.(?=\w)', '', w2)
        return f"{w1_clean} {w2_clean}"

    return patrón.sub(_repl, texto)

# Extración de texto de un PDF + normalización avanzada
def normalizacion_avanzada_pdf(path_pdf: str = None, raw_text: str = None) -> str:
    """
    Extrae todo el texto de un PDF y luego aplica una normalización enfocada
    en facilitar la detección de DNI y matrículas.
    """
    # 1) Obtener texto: o bien del PDF, o bien usar el raw_text
    # 1.1) Detectamos si es un texto plano
    if raw_text is not None:
        texto = raw_text
    elif path_pdf:
        # 1.2) Detectamos si es un .pdf, en ese caso, realizamos la extracción básica de texto del PDF
        texto = ''
        with fitz.open(path_pdf) as doc:
            for pagina in doc:
                texto += pagina.get_text()
    else:
        raise ValueError("Debe proporcionarse 'path_pdf' o 'raw_text'")

    # 2) Unificar sinónimos (case-insensitive), de forma más genérica
    # 2.1) Detectar “Documento Nacional de Identidad” → “DNI”
    texto = re.sub(r'\bDocumento\s+Nacional\s+de\s+Identidad\b', 'DNI', texto, flags=re.IGNORECASE)

    # 2.2) Detectar “Documento Nacional” → “DNI”
    texto = re.sub(r'\bDocumento\s+Nacional\b', 'DNI', texto, flags=re.IGNORECASE)

    # 2.3) Detectar “Documento” solo → “DNI”
    texto = re.sub(r'\bDocumento\b', 'DNI', texto, flags=re.IGNORECASE)

    # 2.4) Detectar variantes de “D.N.I.”, “DN-I”, “D N I”, etc. → “DNI”
    texto = re.sub(r'\bD[\W_]*N[\W_]*I\b', 'DNI', texto, flags=re.IGNORECASE)

    # 2.5) Detectar variantes con puntos, guiones o espacios en C.U.I.T / C.U.I.L / C.U.I.F (con o sin punto final)
    texto = re.sub(r'\bC[\W_]*U[\W_]*I[\W_]*T[\W_\.]*\b', 'CUIT ', texto, flags=re.IGNORECASE)
    texto = re.sub(r'\bC[\W_]*U[\W_]*I[\W_]*L[\W_\.]*\b', 'CUIL ', texto, flags=re.IGNORECASE)
    texto = re.sub(r'\bC[\W_]*U[\W_]*I[\W_]*F[\W_\.]*\b', 'CUIF ', texto, flags=re.IGNORECASE)

    # 2.6) Detectar “Matrícula” con o sin acento → “MATRICULA”
    texto = re.sub(r'\bMatr[ií]cula\b', 'MATRICULA', texto, flags=re.IGNORECASE)

    # 2.7) Variantes de “M.P.”, “M-P-”, “MP” con puntos/guiones/espacios entre letras → “MATRICULA”
    texto = re.sub(r'\bM[\W_]*P\b', 'MATRICULA', texto, flags=re.IGNORECASE)

    # 2.8) Detecta "DNI-", "MATRICULA-", "MATRICULA.", "CUIT-", "CUIL-", "CUIF-" con o sin espacios o guiones especiales
    texto = re.sub(r'\b(DNI|MATRICULA|CUIT|CUIL|CUIF)\s*[-–—\.]\s*', r'\1 ', texto, flags=re.IGNORECASE)

    # 3) Eliminar 'N°', 'Nº', 'N%', 'N”', 'N*' (y variantes con ., : o espacios antes del número)
    texto = re.sub(r'\bN[º°%”*]?[.:,\s-]*\s*(?=\d)', '', texto)

    # 3.1) Eliminar variantes de 'Número' (con o sin acento, plural o abreviado) solo si preceden a un número
    texto = re.sub(r'\bN[úu]m(?:ero|eros|\.?)?\s*[-:]?\s*(?=\d)', '', texto, flags=re.IGNORECASE)

    # 4) Eliminar guiones largos especiales y convertirlos a guiones normales
    # Guiones largos: — (em dash), – (en dash)
    texto = texto.replace('—', '-').replace('–', '-')
    
    # 5) Quitar separadores entre dígitos (., -, /) incluso con espacios
    # Esto convierte: 20-35123456-7 → 20351234567
    texto = re.sub(r'(?<=\d)[\.\-/]\s*(?=\d)', '', texto)
    # También eliminar separadores justo después de dígitos (guiones/puntos/barras finales)
    texto = re.sub(r'(?<=\d)[\.\-/]+(?=\s|[^\d\w]|$)', '', texto)
    
    # 6) Normalizar paréntesis y caracteres especiales alrededor de números
    # Eliminar paréntesis/comillas/corchetes que encierran números
    texto = re.sub(r'(["\(\[\{])\s*(\d+)\s*(["\)\]\}])', r' \2 ', texto)
    # Limpiar caracteres especiales sueltos al inicio/final de números
    texto = re.sub(r'(["\(\[\{])\s*(\d)', r' \2', texto)  # Eliminar apertura antes de dígito
    texto = re.sub(r'(\d)\s*(["\)\]\}])', r'\1 ', texto)  # Eliminar cierre después de dígito

    # 7) Eliminar puntos entre letras (Ej, S.R.L. -> SRL.)
    texto = eliminar_puntos_antes_de_cuit(texto)

    # 8) Asegurar siempre un espacio entre etiqueta y número
    texto = re.sub(r'\b(DNI|MATRICULA)[^\w]*(\d+)\b', r'\1 \2', texto, flags=re.IGNORECASE)
    
    # 9) Eliminar ruido entre etiquetas y sus números. Cubre casos como: CUIT NS 20321777636 → CUIT 20321777636
    texto = re.sub(r'\b(DNI|MATRICULA|CUIT|CUIL|CUIF)\b[^\d\n]{0,10}?(?:\d+[a-z]{1,3}\.?|[a-z]{1,5}\.?)?\s*(?=\d{4,})', r'\1 ', texto, flags=re.IGNORECASE)

    # 10) Colapsar cualquier whitespace a un solo espacio y recortar
    texto = re.sub(r'\s+', ' ', texto).strip()

    return texto