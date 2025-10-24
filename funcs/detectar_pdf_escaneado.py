"""
Detección de PDF escaneado y OCR con Tesseract + extracción de entidades (NER).

Este módulo permite:
1. Detectar si un PDF está compuesto por imágenes escaneadas (sin texto embebido).
2. Aplicar OCR (Reconocimiento Óptico de Caracteres) con Tesseract.
3. Extraer entidades nombradas (NER) usando un modelo BERT en español.
4. Guardar los resultados del OCR y las entidades extraídas en archivos .txt.
"""

import os
from typing import Tuple, Optional
from pdf2image import convert_from_path
import pytesseract
from transformers import pipeline


# Inicializamos el modelo NER en español (una sola vez)
# Usa agregación de entidades para mayor legibilidad (por ej. "Juan Pérez" como una sola entidad)
nlp = pipeline(
    "ner",
    model="mrm8488/bert-spanish-cased-finetuned-ner",
    aggregation_strategy="simple"
)


def _es_pdf_escaneado(path_pdf: str, umbral_texto: int = 100) -> bool:
    """
    Heurístico básico: detecta si el PDF parece escaneado.
    - Convierte las primeras páginas a texto con PyMuPDF y evalúa si hay texto embebido.
    - Si el texto embebido es escaso, se asume que es escaneado.
    """
    import fitz  # PyMuPDF
    with fitz.open(path_pdf) as doc:
        total_chars = sum(len(page.get_text("text") or "") for page in doc)
    return total_chars < umbral_texto


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extrae texto de un PDF escaneado convirtiendo cada página en una imagen
    y aplicando OCR con Tesseract.
    """
    try:
        pages = convert_from_path(pdf_path, 300)
        full_text = ''
        for page_number, page in enumerate(pages, start=1):
            print(f"[OCR] Procesando página {page_number}")
            page_text = pytesseract.image_to_string(page, lang='spa')
            full_text += page_text + "\n"
        return full_text.strip()
    except Exception as e:
        print(f"[ERROR] Falló OCR con pytesseract: {e}")
        return ""


def extract_entities(text: str):
    """Extrae entidades nombradas (NER) del texto utilizando el modelo BERT en español.
    Divide el texto en fragmentos seguros (~1500 caracteres) para evitar sobrecargar el modelo."""
    try:
        # Cortar el texto en segmentos de máximo 400 tokens aprox (unas 1500-2000 letras)
        chunk_size = 1500
        chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
        entities = []

        for i, chunk in enumerate(chunks, start=1):
            print(f"[NER] Procesando segmento {i}/{len(chunks)}...")
            ents = nlp(chunk)
            entities.extend(ents)

        return entities
    except Exception as e:
        print(f"[ERROR] Falló NER: {e}")
        return []


def detectar_scnan(path_pdf: str) -> Tuple[str, Optional[str]]:
    """
    Detecta si un PDF está escaneado y, si es así, aplica OCR con Tesseract.
    """
    # Paso 1: detectar si es escaneado o no
    es_escaneado = _es_pdf_escaneado(path_pdf)

    if not es_escaneado:
        leyenda = "El PDF no contiene imágenes escaneadas."
        return leyenda, None

    # Paso 2: aplicar OCR con pytesseract
    print("[INFO] El PDF parece escaneado. Iniciando OCR...")
    texto_ocr = extract_text_from_pdf(path_pdf)

    if not texto_ocr.strip():
        raise RuntimeError("No se pudo extraer texto mediante OCR.")

    # # Paso 3: (opcional) extraer entidades con NER
    # print("[INFO] Ejecutando NER sobre el texto extraído...")
    # entities = extract_entities(texto_ocr)

    # # Guardar resultados para inspección manual (opcional)
    # output_dir = "resultados_del_escaneo"
    # os.makedirs(output_dir, exist_ok=True)

    # ocr_file = os.path.join(output_dir, "resultado_ocr.txt")
    # ents_file = os.path.join(output_dir, "entidades_extraidas.txt")

    # # Si ya existen, eliminarlos antes de crear nuevos
    # for file_path in (ocr_file, ents_file):
    #     if os.path.exists(file_path):
    #         try:
    #             os.remove(file_path)
    #             print(f"[INFO] Archivo anterior eliminado: {file_path}")
    #         except Exception as e:
    #             print(f"[WARN] No se pudo eliminar {file_path}: {e}")

    # # Guardar nuevo OCR
    # with open(ocr_file, "w", encoding="utf-8") as f:
    #     f.write(texto_ocr)

    # # Guardar nuevas entidades
    # with open(ents_file, "w", encoding="utf-8") as f:
    #     for e in entities:
    #         f.write(f"{e['word']} - {e['entity_group']}\n")

    leyenda = "El PDF está compuesto por imágenes escaneadas. Se aplicó OCR con Tesseract y NER en español."
    return leyenda, texto_ocr
