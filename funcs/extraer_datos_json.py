"""
Lee un archivo de texto con formato JSON, carga su contenido en un diccionario y recorre recursivamente cada valor (en el nivel raíz, en listas y en diccionarios anidados) para normalizarlo. 
La normalización elimina espacios múltiples y aplica strip a los strings para dejarlos listos para su posterior procesamiento.
"""
import json
import re # Se usara para buscar patrones en el texto extraído del PDF

def extraer_valores_txt(path_txt='datos.txt'):
    with open(path_txt, 'r', encoding='utf-8-sig') as file: # Se usa utf-8-sig para evitar problemas con BOM
        datos = json.load(file)

    # Normalizar los valores eliminando espacios múltiples y aplicando strip
    def normalizar_valor(val):
        if isinstance(val, str):
            val = re.sub(r'\s+', ' ', val).strip()
        return val

    # Aplicamos la normalización a todos los valores en listas y diccionarios
    for seccion, lista in datos.items():
        if isinstance(lista, list):
            for elemento in lista:
                for clave in list(elemento.keys()):
                    valor_normalizado = normalizar_valor(elemento[clave])
                    elemento[clave] = valor_normalizado
        elif isinstance(lista, dict):
            for clave in list(lista.keys()):
                valor_normalizado = normalizar_valor(lista[clave])
                lista[clave] = valor_normalizado
    
    # Normalizar claves al nivel raíz que no son listas ni diccionarios
    for clave in list(datos.keys()):
        valor = datos[clave]
        if not isinstance(valor, (list, dict)):
            datos[clave] = normalizar_valor(valor)

    return datos
