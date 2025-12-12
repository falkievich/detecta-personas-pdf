"""
Carga un archivo JSON y un PDF, extrae valores del JSON (en la raíz, diccionarios o listas) y del PDF (numéricos y texto),
calcula la similitud entre cada par JSON ↔ PDF con reglas más estrictas (acentos/normalización, solapamiento de tokens),
etiqueta por umbrales (sin lógica difusa) y agrupa en exacta, alta, media y baja.
"""
import re
import os
from rapidfuzz import fuzz
from funcs.extraer_datos_json import extraer_valores_txt
from funcs.normalizacion.normalizar_y_extraer_texto_pdf import normalizacion_simple_pdf
from funcs.comparar_palabras import compare_text_preciso  # comparador robusto de texto
from funcs.etiquetas import label_from_score  # umbrales/etiquetado
from funcs.normalizacion.normalizacion_txt_json import normalizar_para_comparacion

# Regex para extraer números (con o sin separadores)
# Acepta números de 1+ dígitos, opcionalmente con separadores de miles/puntos/guiones
NUM_REGEX = re.compile(r"\b\d+(?:[.\-]\d+)*\b")

def comparar_valores_json_pdf(json_path: str, source_path: str):
    """
    Compara valores de un archivo JSON con el contenido de un PDF o TXT.
    
    Args:
        json_path: Ruta al archivo JSON o TXT con datos de referencia
        source_path: Ruta al archivo PDF o TXT a comparar
    
    Returns:
        Diccionario con las comparaciones agrupadas por nivel de similitud
    """
    json_data = extraer_valores_txt(json_path)
    if not json_data:
        return {"exacta": [], "alta": [], "media": [], "baja": []}

    # Detectar si el archivo fuente es TXT o PDF por su extensión
    ext = os.path.splitext(source_path)[1].lower()
    
    if ext == '.txt':
        # Leer el contenido del archivo TXT directamente
        with open(source_path, 'r', encoding='utf-8') as f:
            texto_pdf_original = f.read()
        # Aplicar normalización simple al texto
        texto_pdf_original = texto_pdf_original.replace('\n', ' ').replace('\r', ' ')
        texto_pdf_original = re.sub(r'\s+', ' ', texto_pdf_original).strip()
    else:
        # Extraer texto original del PDF (para mostrar)
        texto_pdf_original = normalizacion_simple_pdf(path_pdf=source_path)
    
    # Normalizar para comparación (sin separadores en números)
    texto_pdf_comparacion = normalizar_para_comparacion(texto_pdf_original)
    
    # print("texto pdf para mostrar: ", texto_pdf_original, "\n")
    # print("\n\ntexto pdf para comparar: ", texto_pdf_comparacion)


    words_original = texto_pdf_original.split()
    words_comparacion = texto_pdf_comparacion.split()

    # Lista plana de todas las comparaciones
    all_comparisons = []

    # Recorremos todos los campos del JSON (raíz, dicts o listas)
    for key, value in json_data.items():
        # Preparamos la lista de valores a comparar, conservando el "path" del campo
        items = []
        if isinstance(value, dict):
            for subkey, subval in value.items():
                items.append((f"{key} - {subkey}", subval))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    for subkey, subval in item.items():
                        items.append((f"{key} - {subkey}", subval))
                else:
                    items.append((key, item))
        else:
            items.append((key, value))

        for field_display, val in items:
            val_str = str(val).strip()
            if not val_str:
                continue

            # Normalizar el valor del JSON para comparación
            val_str_comparacion = normalizar_para_comparacion(val_str)

            best_score, best = 0.0, None

            # 1) Detectar si es puramente numérico (solo dígitos y separadores)
            # Si tiene letras (como "DNI-123"), se trata como TEXTO
            es_solo_numerico = bool(re.match(r'^[\d\.\-\s]+$', val_str.strip()))
            
            if es_solo_numerico:
                # --------- Comparación de NUMÉRICOS PUROS (insensible a separadores) ----------
                # Busca números en el PDF normalizado (sin separadores)
                candidates = NUM_REGEX.findall(texto_pdf_comparacion)
                
                # Limpiar el valor JSON (solo dígitos)
                clean_json = re.sub(r"\D", "", val_str_comparacion)
                
                local_best = -1.0
                local_best_span = None
                
                if candidates:
                    for tok in candidates:
                        # Limpiar el candidato del PDF (solo dígitos)
                        clean_tok = re.sub(r"\D", "", tok)
                        
                        # Comparar SOLO los dígitos
                        if clean_json == clean_tok:
                            sc = 100.0
                        else:
                            sc = fuzz.ratio(clean_json, clean_tok)
                        
                        if sc > local_best:
                            local_best = sc
                            local_best_span = tok
                        if local_best == 100.0:
                            break
                
                best_score = float(local_best if local_best >= 0 else 0.0)
                best = local_best_span

            else:
                # --------- Comparación de TEXTO (normaliza acentos, tokens, overlap) ----
                # Pasar texto_pdf_comparacion (normalizado) para comparar
                # y texto_pdf_original para extraer el span a mostrar
                best_score, best = compare_text_preciso(val_str, texto_pdf_comparacion, texto_pdf_original)

                # Fallback opcional: si no hay candidato, probá n-grama plano simple
                if best is None:
                    n = max(1, len(val_str_comparacion.split()))
                    json_norm = val_str_comparacion.lower()
                    json_norm_len = len(json_norm)
                    min_len_required = int(json_norm_len * 0.7)  # Al menos 70% de la longitud
                    
                    local_best = -1.0
                    local_best_span = None
                    local_best_idx = -1
                    
                    for i in range(0, len(words_comparacion) - n + 1):
                        cand = ' '.join(words_comparacion[i:i+n])
                        cand_lower = cand.lower()
                        
                        # FILTRO: Solo comparar si el candidato tiene longitud similar
                        if len(cand_lower) < min_len_required:
                            continue
                        
                        sc = fuzz.ratio(json_norm, cand_lower)
                        if sc > local_best:
                            local_best = sc
                            local_best_idx = i
                        if local_best == 100.0:
                            break
                    
                    if local_best > best_score:
                        best_score = float(local_best if local_best >= 0 else 0.0)
                        # Obtener el span original del PDF para mostrar
                        if local_best_idx >= 0 and local_best_idx + n <= len(words_original):
                            local_best_span = ' '.join(words_original[local_best_idx:local_best_idx+n])
                        best = local_best_span

            # 2) Etiqueta por umbrales
            etiqueta = label_from_score(best_score)

            # 3) Añadir a la lista general (con valores ORIGINALES para mostrar)
            all_comparisons.append({
                "field": field_display,
                "json_value": val_str,    # Valor original del JSON
                "pdf_value": best,        # Valor original del PDF
                "similarity": round(best_score, 2),
                "label": etiqueta
            })

    # 4) Agrupar por categoría y ordenar cada grupo de mayor a menor similitud
    exacta = [c for c in all_comparisons if c["label"] == "exacta"]
    alta = [c for c in all_comparisons if c["label"] == "alta"]
    media = [c for c in all_comparisons if c["label"] == "media"]
    baja = [c for c in all_comparisons if c["label"] == "baja"]
    
    # Ordenar cada categoría por similarity descendente (mayor a menor)
    exacta.sort(key=lambda x: x["similarity"], reverse=True)
    alta.sort(key=lambda x: x["similarity"], reverse=True)
    media.sort(key=lambda x: x["similarity"], reverse=True)
    baja.sort(key=lambda x: x["similarity"], reverse=True)
    
    result = {
        "exacta": exacta,
        "alta": alta,
        "media": media,
        "baja": baja,
    }
    return result
