# funcs/comparar_palabras.py
"""
Comparación robusta de palabras/frases:
- Normaliza (sin acentos, minúsculas, sin signos).
- Prefiltra por intersección de tokens para reducir falsos positivos.
- Exact match acento-insensible => 100.
- Usa rapidfuzz: ratio (1 palabra) o token_set_ratio (frases).
"""

import re
from typing import Tuple, Optional
from rapidfuzz import fuzz
from funcs.normalizacion.normalizacion_txt_json import strip_accents_lower, tokenize_text, has_token_overlap, normalizar_para_comparacion


def compare_text_preciso(target: str, full_text: str, full_text_original: str = None) -> Tuple[float, Optional[str]]:
    # Normalizar el target primero con normalizar_para_comparacion para eliminar puntos entre dígitos
    target_normalized = normalizar_para_comparacion(target)
    target_norm = strip_accents_lower(target_normalized)
    if not target_norm:
        return 0.0, None

    # Si no se proporciona texto original, usar el mismo texto normalizado
    if full_text_original is None:
        full_text_original = full_text

    # A) Tokens para la VENTANA (NO quitar stopwords)
    target_tokens_full = target_norm.split()
    if not target_tokens_full:
        return 0.0, None
    n = len(target_tokens_full)

    # B) Tokens para el FILTRO de solapamiento (SÍ quitar stopwords)
    target_tokens_overlap = tokenize_text(target, remove_stopwords=True)

    # CAMBIO: Usar el texto normalizado (full_text) para devolver spans
    # en lugar del original, para evitar fragmentación
    words_normalized = full_text.split()
    words_norm = [strip_accents_lower(w) for w in words_normalized]

    best_score = -1.0
    best_span: Optional[str] = None
    
    # Si el target tiene números largos (6+ dígitos, con o sin separadores), extenderemos la ventana
    # para capturar contexto adicional (ej: "DNI N° 123456" en vez de solo "DNI N°")
    # Buscar tanto números consecutivos como números con separadores (puntos, guiones)
    has_long_number = bool(re.search(r'\d{6,}', target)) or bool(re.search(r'\d[\d.\-]{5,}\d', target))
    
    if has_long_number:
        # Si el target tiene formato "DNI-123456" (2 tokens), buscar ventanas más grandes
        # porque en el PDF puede aparecer como "DNI N° 123456" (3-4 tokens)
        # Limitar a n+1 para evitar capturar demasiado contexto irrelevante
        max_window = n + 1
    else:
        max_window = n

    for window_size in range(n, max_window + 1):
        for i in range(0, len(words_norm) - window_size + 1):
            cand_norm = " ".join(words_norm[i:i+window_size]).strip()
            cand_original = " ".join(words_normalized[i:i+window_size]).strip()

            # Filtro de solapamiento con stopwords removidas SOLO para el chequeo
            cand_tokens_overlap = tokenize_text(cand_norm, remove_stopwords=True)
            if not has_token_overlap(target_tokens_overlap, cand_tokens_overlap):
                continue

            # Scoring sobre los textos normalizados completos (con stopwords)
            if n == 1 and len(cand_norm.split()) == 1:
                sc = fuzz.ratio(target_norm, cand_norm)
            else:
                # Si el target tiene números largos, usar ratio (más estricto)
                # en vez de token_set_ratio para evitar falsos 100%
                if has_long_number:
                    sc = fuzz.ratio(target_norm, cand_norm)
                else:
                    sc = fuzz.token_set_ratio(target_norm, cand_norm)

            if target_norm == cand_norm:
                sc = 100.0


            if sc > best_score:
                best_score = sc
                best_span = cand_original

            if best_score == 100.0:
                break
        
        if best_score == 100.0:
            break

    if best_score < 0:
        return 0.0, None
    return float(best_score), best_span
