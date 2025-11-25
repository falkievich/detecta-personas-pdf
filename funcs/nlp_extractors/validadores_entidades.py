"""
Validadores para entidades (DNI, CUIL, CUIT, CUIF, Matrícula).
Implementa validación estricta de formatos según normativas argentinas.
"""
import re


def validar_dni(numero: str) -> bool:
    """
    Valida formato de DNI argentino.
    - Solo números
    - Longitud: 7 u 8 dígitos
    """
    numero_limpio = re.sub(r'\D', '', numero)
    return len(numero_limpio) in (7, 8) and numero_limpio.isdigit()


def validar_cuil(numero: str) -> bool:
    """
    Valida formato de CUIL argentino.
    - Longitud: 11 dígitos
    - Prefijos válidos: 20, 23, 24, 27
    - Estructura: AA-BBBBBBBB-C
    """
    numero_limpio = re.sub(r'\D', '', numero)
    
    if len(numero_limpio) != 11:
        return False
    
    prefijo = int(numero_limpio[:2])
    if prefijo not in (20, 23, 24, 27):
        return False
    
    # Validar dígito verificador (módulo 11)
    return _validar_digito_verificador(numero_limpio)


def validar_cuit(numero: str) -> bool:
    """
    Valida formato de CUIT argentino.
    - Longitud: 11 dígitos
    - Prefijos válidos: 20, 23, 24, 27 (personas físicas), 30, 33, 34 (jurídicas)
    - Estructura: AA-BBBBBBBB-C
    """
    numero_limpio = re.sub(r'\D', '', numero)
    
    if len(numero_limpio) != 11:
        return False
    
    prefijo = int(numero_limpio[:2])
    if prefijo not in (20, 23, 24, 27, 30, 33, 34):
        return False
    
    # Validar dígito verificador (módulo 11)
    return _validar_digito_verificador(numero_limpio)


def validar_cuif(numero: str) -> bool:
    """
    Valida formato de CUIF (Clave Única de Identificación Forum).
    - Solo números
    - Longitud: 1 a 10 dígitos
    - Sin formato estructurado
    """
    numero_limpio = re.sub(r'\D', '', numero)
    return 1 <= len(numero_limpio) <= 10 and numero_limpio.isdigit()


def validar_matricula(codigo: str) -> bool:
    """
    Valida formato de Matrícula profesional.
    - Alfanumérico
    - Longitud: 1 a 10 caracteres
    - Sin caracteres especiales (solo letras y números)
    """
    codigo_limpio = re.sub(r'[^A-Za-z0-9]', '', codigo)
    return 1 <= len(codigo_limpio) <= 10 and codigo_limpio.isalnum()


def _validar_digito_verificador(numero: str) -> bool:
    """
    Valida el dígito verificador de CUIT/CUIL usando módulo 11.
    
    Args:
        numero: String de 11 dígitos (sin separadores)
    
    Returns:
        True si el dígito verificador es correcto
    """
    if len(numero) != 11:
        return False
    
    # Secuencia de multiplicadores para módulo 11
    multiplicadores = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    
    try:
        # Calcular suma ponderada
        suma = sum(int(numero[i]) * multiplicadores[i] for i in range(10))
        
        # Calcular dígito verificador esperado
        resto = suma % 11
        digito_esperado = 11 - resto
        
        # Casos especiales
        if digito_esperado == 11:
            digito_esperado = 0
        elif digito_esperado == 10:
            digito_esperado = 9
        
        # Comparar con el dígito verificador real
        return int(numero[10]) == digito_esperado
    except (ValueError, IndexError):
        return False
