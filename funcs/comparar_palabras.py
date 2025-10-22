# funcs/comparar_palabras.py
"""
Comparación robusta de palabras/frases:
- Normaliza (sin acentos, minúsculas, sin signos).
- Prefiltra por intersección de tokens para reducir falsos positivos.
- Exact match acento-insensible => 100.
- Usa rapidfuzz: ratio (1 palabra) o token_set_ratio (frases).
"""

from typing import Tuple, Optional
from rapidfuzz import fuzz
from funcs.normalizacion.normalizacion_txt_json import strip_accents_lower, tokenize_text, has_token_overlap


def compare_text_preciso(target: str, full_text: str) -> Tuple[float, Optional[str]]:
    target_norm = strip_accents_lower(target)
    if not target_norm:
        return 0.0, None

    # A) Tokens para la VENTANA (NO quitar stopwords)
    target_tokens_full = target_norm.split()
    if not target_tokens_full:
        return 0.0, None
    n = len(target_tokens_full)

    # B) Tokens para el FILTRO de solapamiento (SÍ quitar stopwords)
    target_tokens_overlap = tokenize_text(target, remove_stopwords=True)

    words_original = full_text.split()
    words_norm = [strip_accents_lower(w) for w in words_original]

    best_score = -1.0
    best_span: Optional[str] = None

    for i in range(0, len(words_norm) - n + 1):
        cand_norm = " ".join(words_norm[i:i+n]).strip()
        cand_original = " ".join(words_original[i:i+n]).strip()

        # Filtro de solapamiento con stopwords removidas SOLO para el chequeo
        cand_tokens_overlap = tokenize_text(cand_norm, remove_stopwords=True)
        if not has_token_overlap(target_tokens_overlap, cand_tokens_overlap):
            continue

        # Scoring sobre los textos normalizados completos (con stopwords)
        if n == 1 and len(cand_norm.split()) == 1:
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

    if best_score < 0:
        return 0.0, None
    return float(best_score), best_span
