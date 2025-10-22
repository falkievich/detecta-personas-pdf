# funcs/etiquetas.py
"""
Etiquetado determinístico por umbrales.
Ajustá TH_EXACTA / TH_ALTA / TH_MEDIA según la tolerancia establecida.
"""

TH_EXACTA = 99.9
TH_ALTA   = 85.0
TH_MEDIA  = 70.0

def label_from_score(score: float) -> str:
    """
    100 => exacta; >=85 => alta; >=70 => media; <70 => baja.
    """
    if score >= TH_EXACTA:
        return "exacta"
    if score >= TH_ALTA:
        return "alta"
    if score >= TH_MEDIA:
        return "media"
    return "baja"
