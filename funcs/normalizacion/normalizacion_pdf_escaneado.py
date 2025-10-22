"""
Normalización avanzada para texto proveniente de OCR.
Se usa solo cuando el PDF fue escaneado (texto_ocr).
Más tolerante a errores de OCR y caracteres mal reconocidos.
"""
import re


def normalizacion_ocr_pdf(raw_text: str) -> str:
    """
    Limpia y normaliza texto proveniente de OCR:
    - Corrige variantes incompletas o distorsionadas de 'Documento Nacional de Identidad'
    - Elimina frases como 'Escaneado con CamScanner'
    - Elimina símbolos o caracteres especiales innecesarios
    - Corrige casos parciales como 'DNI Naciona'
    """

    texto = raw_text

    # 1️) Eliminar frases automáticas de apps de escaneo
    texto = re.sub(r'Escaneado\s+con\s+CamScanner', '', texto, flags=re.IGNORECASE)
    texto = re.sub(r'CamScanner', '', texto, flags=re.IGNORECASE)

    # 2️) Eliminar caracteres o símbolos raros del OCR
    # (€, *, ", ', @, `, ^, ~, =, +, etc.)
    texto = re.sub(r'[€*"\',@`^~+=<>·•■□●○◆◇¤¢¿¡§¨©«»°]', ' ', texto)

    # 3️.1) Tolerar errores de OCR en “Documento Nacional de Identidad”
    # Detecta variantes deformadas (documen, docum, docume; naciona, nacional; identida, identidad)
    texto = re.sub(
        r'\bDocu\w*\s+Nacion\w*\s+(de\s+)?Ident\w*\b',
        'DNI',
        texto,
        flags=re.IGNORECASE
    )

    # 3.2) Tolerar variantes parciales como “Documento Nacional”, “Docum Naciona”
    texto = re.sub(
        r'\bDocu\w*\s+Nacion\w*\b',
        'DNI',
        texto,
        flags=re.IGNORECASE
    )

    # 3.3) Tolerar “Documento” o “Docum” solo
    texto = re.sub(
        r'\bDocu\w*\b',
        'DNI',
        texto,
        flags=re.IGNORECASE
    )

    # 3.4) Corregir casos como “DNI Naciona” → “DNI”
    texto = re.sub(
        r'\bDNI\s+Nacion\w*\b',
        'DNI',
        texto,
        flags=re.IGNORECASE
    )

    # 4) Eliminar ruido entre etiquetas y sus números. Cubre casos como: CUIT NS 20321777636 → CUIT 20321777636
    texto = re.sub(r'\b(DNI|MATRICULA|CUIT|CUIL|CUIF)\b[^0-9]{0,6}(?=\s*\d{4,})', r'\1 ', texto, flags=re.IGNORECASE)

    # 4.1) Unir números partidos (como "20373 773") después de etiquetas conocidas (DNI, CUIL, CUIT, CUIF)
    texto = re.sub(r'\b(DNI|CUIL|CUIT|CUIF)\s+(\d{2,5})\s+(\d{3,5})(?!\d)', lambda m: f"{m.group(1)} {m.group(2)}{m.group(3)}", texto, flags=re.IGNORECASE)

    # 5) Eliminar repeticiones o espacios dobles
    texto = re.sub(r'\s+', ' ', texto).strip()

    return texto
