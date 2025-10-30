"""
Funciones de normalización de texto para comparación de datos JSON/TXT.
Incluye normalización simple, eliminación de acentos, tokenización y filtrado de stopwords.
"""

import re
import unicodedata
from typing import List, Set

# Stopwords para filtrado
STOPWORDS_ES: Set[str] = {
    "de", "la", "el", "los", "las", "y", "o", "u", "a", "en", "del",
    "al", "por", "para", "con", "sin", "un", "una", "uno", "unos", "unas",
    "su", "sus", "mi", "mis", "tu", "tus", "se", "es", "son"
}

# Regex para eliminar caracteres no alfanuméricos (tras normalizar)
NON_ALNUM = re.compile(r"[^0-9a-z]+")


def strip_accents_lower(s: str) -> str:
    """
    Normaliza un texto: elimina acentos, convierte a minúsculas,
    deja solo caracteres alfanuméricos y espacios, colapsa espacios múltiples.
    """
    # NFKD + quita marcas diacríticas + lowercase
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    s = s.lower()
    # deja solo [0-9a-z] y espacios
    s = NON_ALNUM.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def tokenize_text(s: str, remove_stopwords: bool = True) -> List[str]:
    """
    Tokeniza un texto normalizado en palabras individuales. Remueve stopwords.

    Returns:
        Lista de tokens (palabras)
    """
    toks = strip_accents_lower(s).split()
    if remove_stopwords:
        toks = [t for t in toks if t not in STOPWORDS_ES]
    return toks


def has_token_overlap(a_tokens: List[str], b_tokens: List[str]) -> bool:
    """
    Verifica si dos listas de tokens tienen al menos 1 token en común
    o comparten un prefijo de al menos 3 caracteres.
    
    Args:
        a_tokens: Primera lista de tokens
        b_tokens: Segunda lista de tokens
        
    Returns:
        True si hay solapamiento, False en caso contrario
    """
    set_a = set(a_tokens)
    set_b = set(b_tokens)
    
    # Intersección directa
    if set_a & set_b:
        return True
    
    # Si no hay intersección exacta, probar prefijo >= 3
    for ta in set_a:
        for tb in set_b:
            if len(ta) >= 3 and len(tb) >= 3 and (ta.startswith(tb) or tb.startswith(ta)):
                return True
    
    return False


def normalizar_para_comparacion(texto: str) -> str:
    """
    Normalización específica para comparación: elimina puntos, guiones y espacios
    entre dígitos.
    También elimina saltos de línea, caracteres especiales inválidos y colapsa espacios múltiples.
    """
    # Eliminar caracteres de reemplazo Unicode inválidos
    texto = texto.replace('\ufffd', '').replace('�', '')

    # Normalizar forma canónica (evita variantes visuales raras de bullets/espacios)
    try:
        texto = unicodedata.normalize("NFKC", texto)
    except Exception:
        pass

    # Eliminar otros caracteres de control y especiales problemáticos
    texto = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]', '', texto)

    # Remover marcadores de lista/viñetas comunes (Word/PDF/PUA) cuando actúan como bullets
    BULLETS_REGEX = r'(?:(?<=^)|(?<=\s))[\-\*\u2022\u2023\u25E6\u2043\u2219\u25AA\u25CF\u25CB\u25A0\u00B7\u204C\u204D\u2219\uF0B7\uF0A7\uF076](?=\s)'
    texto = re.sub(BULLETS_REGEX, ' ', texto)

    # Eliminar saltos de línea y colapsar espacios
    texto = texto.replace('\n', ' ').replace('\r', ' ')
    texto = re.sub(r'\s+', ' ', texto).strip()

    # Eliminar puntos entre letras (ej: d.n.i → dni)
    texto = re.sub(r'(?<=[a-zA-Z])\.(?=[a-zA-Z])', '', texto)
    
    # Eliminar corchetes, paréntesis y otros caracteres de puntuación comunes
    texto = re.sub(r'[\[\]\(\)\{\}]', ' ', texto)
    
    # Eliminar comas, punto y coma al final de palabras
    texto = re.sub(r'[,;](?=\s|$)', '', texto)
    
    # Colapsar espacios múltiples que puedan haber quedado
    texto = re.sub(r'\s+', ' ', texto).strip()

    # Eliminar puntos, guiones, barras y espacios entre dígitos (separadores de miles)
    texto = re.sub(r'(?<=\d)[.\-/\s]+(?=\d)', '', texto)

    return texto
