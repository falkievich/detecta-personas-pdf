"""
Módulo para parsear y normalizar la entrada de entidades desde diferentes formatos.
Soporta múltiples formatos de entrada desde Postman (form-data, JSON, CSV).
"""
import json
from typing import List, Optional


def parse_entities_input(entities_input: Optional[List[str]]) -> List[str]:
    """
    Normaliza la entrada `entities` que puede llegar de varias formas desde Postman:
      - Repetición de keys en form-data -> List[str] (ok)
      - Un único campo form-data con valor '["dni","nombre"]' -> List[str] con 1 elemento (JSON string)
      - Un único campo form-data con valor 'dni,nombre' -> List[str] separado por comas
      - En JSON body llega como lista -> List[str]
    
    Args:
        entities_input: Entrada de entidades en formato variable
        
    Returns:
        Lista de entidades en minúsculas y limpias
        
    Examples:
        >>> parse_entities_input(["dni", "nombre"])
        ['dni', 'nombre']
    """
    if entities_input is None:
        return []
    
    # Si ya es lista con varios elementos normales
    if isinstance(entities_input, list) and len(entities_input) > 1:
        return [e.strip().lower() for e in entities_input if isinstance(e, str) and e.strip()]

    # Si es lista con un único elemento, o un string único
    single = None
    if isinstance(entities_input, list) and len(entities_input) == 1:
        single = entities_input[0]
    elif isinstance(entities_input, str):
        single = entities_input

    if single is None:
        return []

    raw = single.strip()
    
    # Intentar parsear JSON array
    if raw.startswith("[") and raw.endswith("]"):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(x).strip().lower() for x in parsed if str(x).strip()]
        except Exception:
            # Si falla, seguir intentando otros formatos
            pass

    # Si viene separado por comas
    if "," in raw:
        parts = [p.strip().strip('"').strip("'") for p in raw.split(",") if p.strip()]
        return [p.lower() for p in parts]

    # Valor único
    return [raw.lower()] if raw else []
