"""
Define funciones de lógica difusa mediante funciones de membresía triangular (baja, media, alta, exacta), realiza la inferencia difusa a partir de un porcentaje de similitud y calcula un valor crisp mediante defuzzificación por centro de gravedad.
"""
from typing import Callable, Dict, Tuple

# Función de membresía triangular
def triangular_mf(a: float, b: float, c: float) -> Callable[[float], float]:
    def mf(x: float) -> float:
        if x < a or x > c:
            return 0.0
        if x == b:
            return 1.0
        if a < b and x < b:
            return (x - a) / (b - a)
        if b < c and x > b:
            return (c - x) / (c - b)
        return 0.0
    return mf

# Definición de categorías fuzzy (0-100%)
baja_mf = triangular_mf(0.0, 0.0, 30.0) # de 0 a 30
media_mf = triangular_mf(30.0, 50.0, 70.0) # de 30 a 70
alta_mf = triangular_mf(70.0, 82.5, 95.0) # de 70 a 95
exacta_mf = triangular_mf(95.0, 100.0, 100.0) # de 95 a 100

# Picos representativos para defuzzificación
PEAKS = {'baja': 0.0, 'media': 50.0, 'alta': 82.5, 'exacta': 100.0}

def defuzzify(memberships: Dict[str, float]) -> float:
    numerator = sum(PEAKS[k] * v for k, v in memberships.items())
    denominator = sum(memberships.values())
    return numerator / denominator if denominator else 0.0

# Motor de inferencia: etiqueta y valor (crisp)
def infer_label(similarity: float) -> Tuple[str, float]:
    memberships = {
        'baja': baja_mf(similarity),
        'media': media_mf(similarity),
        'alta': alta_mf(similarity),
        'exacta': exacta_mf(similarity)
    }
    label = max(memberships, key=memberships.get)
    crisp = defuzzify(memberships)
    return label, crisp
