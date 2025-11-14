"""
Módulo para extraer entidades específicas de un PDF usando spaCy.
Permite seleccionar qué tipo de entidades se desean extraer:
- Nombres (personas) - Enfoque híbrido: Regex + spaCy NER
  * Captura nombres completos incluso con puntuación intermedia
  * Usa STOP_WORDS como anclas contextuales (no las elimina del nombre)
- DNI (7-8 dígitos)
- Matrícula (alfanumérico, hasta 10 caracteres)
- CUIF (numérico, 1-10 dígitos)
- CUIT (11 dígitos, prefijos válidos: 20-27, 30, 33-34)
- CUIL (11 dígitos, prefijos válidos: 20, 23-24, 27)

Reutiliza constantes y validadores compartidos para evitar duplicación de código.
"""
import re
import os
from typing import List, Dict, Optional, Tuple, Any
import spacy
# Visualización movida a un módulo separado (import opcional)
try:
    from funcs.nlp_extractors.visualization_displacy import (
        render_and_maybe_save,
        is_visualization_enabled,
        is_save_enabled,
    )
    _VIS_DISPONIBLE = True
except Exception:
    # stub para no romper si se elimina el módulo de visualización en producción
    def render_and_maybe_save(*args, **kwargs):
        return {"error": "visualization_disabled", "note": "Visualization module not available"}
    def is_visualization_enabled():
        return False

    def is_save_enabled():
        return False

    _VIS_DISPONIBLE = False

from funcs.normalizacion.normalizar_y_extraer_texto_pdf import (
    normalizacion_avanzada_pdf
)
from funcs.nlp_extractors.constantes import PATRONES_DOCUMENTOS, STOP_WORDS, ANCLAS_CONTEXTUALES
from funcs.nlp_extractors.validadores_entidades import (
    validar_dni, validar_cuil, validar_cuit, 
    validar_cuif, validar_matricula
)


_nlp = None

def _get_nlp():
    """
    Carga el pipeline de spaCy de forma lazy.
    Usa el modelo es_core_news_md o es_core_news_lg si está disponible.
    """
    global _nlp
    if _nlp is None:
        try:
            # Intentar cargar el modelo grande primero, luego el mediano
            try:
                _nlp = spacy.load("es_core_news_lg")
            except OSError:
                _nlp = spacy.load("es_core_news_md")
        except Exception as e:
            raise RuntimeError(
                f"No se pudo cargar el modelo de spaCy: {e}. "
                "Ejecuta: python -m spacy download es_core_news_md"
            )
    return _nlp



def extraer_entidades_especificas(
    entidades_solicitadas: List[str],
    path_pdf: str,
    # Parámetros de visualización: si se pasan explícitamente (True/False) se respetan;
    # si se dejan como None, se utilizará la configuración global en visualization_displacy.py
    visualizar: Optional[bool] = None,
    vis_style: Optional[str] = None,
    vis_serve: bool = False,
    vis_options: Optional[Dict[str, Any]] = None,
    vis_save: Optional[bool] = None,
    vis_save_dir: Optional[str] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Extrae entidades específicas de un PDF según lo solicitado.
    IMPORTANTE: Usa dos versiones del texto:
    - texto_crudo: para spaCy NER (nombres)
    - texto_normalizado: para documentos (DNI, CUIT, etc.)
    """
    # Validar entrada
    if not path_pdf:
        raise ValueError("Se debe pasar path_pdf")
    
    # Normalizar entidades solicitadas
    entidades_solicitadas = [e.lower().strip() for e in entidades_solicitadas]
    
    # Validar entidades
    entidades_validas = {"nombre", "nombres", "dni", "matricula", "cuif", "cuit", "cuil"}
    entidades_invalidas = set(entidades_solicitadas) - entidades_validas
    if entidades_invalidas:
        raise ValueError(
            f"Entidades no válidas: {', '.join(entidades_invalidas)}. "
            f"Entidades válidas: {', '.join(sorted(entidades_validas))}"
        )
    
    # Normalizar "nombres" a "nombre"
    if "nombres" in entidades_solicitadas:
        entidades_solicitadas.append("nombre")
        entidades_solicitadas.remove("nombres")
    
    # ========== SEPARACIÓN DE TEXTOS ==========
    # Extraer texto NORMALIZADO para todo el flujo (no se usa extraer_texto_crudo_pdf)
    # Usamos el texto normalizado tanto para la extracción de documentos como
    # para el procesamiento con spaCy (si corresponde).
    print("[DEBUG] Extrayendo texto NORMALIZADO del PDF (usado para todo)...")
    texto_normalizado = normalizacion_avanzada_pdf(path_pdf=path_pdf)
    print(f"[DEBUG] Texto NORMALIZADO extraído: {len(texto_normalizado)} caracteres")
    # Reutilizar texto_normalizado como texto_crudo para spaCy
    texto_crudo = texto_normalizado

    # Procesar con spaCy SOLO si se necesitan nombres o si la visualización está activa
    # Si 'visualizar' es None, usamos la configuración global de visualization_displacy
    doc = None
    debe_procesar_spacy = False
    if "nombre" in entidades_solicitadas:
        debe_procesar_spacy = True
    elif visualizar is not None:
        debe_procesar_spacy = bool(visualizar)
    else:
        # usar configuración global si el módulo de visualización está disponible
        debe_procesar_spacy = _VIS_DISPONIBLE and is_visualization_enabled()

    if debe_procesar_spacy:
        print("[DEBUG] Procesando texto CRUDO con spaCy...")
        nlp = _get_nlp()
        doc = nlp(texto_crudo)  # ← SIEMPRE texto_crudo
        print(f"[DEBUG] spaCy procesó {len(doc)} tokens")
    
    # Estructura de resultado
    resultado: Dict[str, List[Dict[str, Any]]] = {}
    
    # ========== EXTRACCIÓN DE NOMBRES (USA TEXTO CRUDO) ==========
    if "nombre" in entidades_solicitadas:
        print("[DEBUG] Extrayendo NOMBRES con texto CRUDO...")
        resultado["nombres"] = _extraer_nombres_con_contexto(
            texto_crudo,  # ← TEXTO CRUDO
            doc=doc
        )
        print(f"[DEBUG] Nombres encontrados: {len(resultado['nombres'])}")
    
    # ========== EXTRACCIÓN DE DOCUMENTOS (USA TEXTO NORMALIZADO) ==========
    for entidad in entidades_solicitadas:
        if entidad == "nombre":
            continue  # Ya procesado arriba
            
        entidad_key = entidad.upper()
        if entidad_key in PATRONES_DOCUMENTOS:
            print(f"[DEBUG] Extrayendo {entidad_key} con texto NORMALIZADO...")
            resultado[entidad] = _extraer_y_validar_documento(
                texto_normalizado,  # ← TEXTO NORMALIZADO
                entidad
            )
            print(f"[DEBUG] {entidad_key} encontrados: {len(resultado[entidad])}")

    # Generar visualización: respetar parámetro explícito si se pasó, sino usar config global
    debe_visualizar = False
    if visualizar is not None:
        debe_visualizar = bool(visualizar)
    else:
        debe_visualizar = _VIS_DISPONIBLE and is_visualization_enabled()
    
    if debe_visualizar and doc is not None:
        # Generar visualización pero NO incluir el HTML ni rutas en la respuesta API
        print("[DEBUG] Generando visualización con displaCy (no incluida en la respuesta)...")
        try:
            # Llamamos al render y guardado si corresponde, pero descartamos el resultado
            _ = render_and_maybe_save(
                doc,
                style=vis_style,
                options=vis_options,
                serve=vis_serve,
                save=vis_save,
                save_dir=vis_save_dir,
            )
        except Exception as e:
            # No queremos que un fallo de visualización afecte la respuesta principal
            print(f"[DEBUG] Error al generar visualización (se ignorará): {e}")

    return resultado


def _extraer_nombres_con_contexto(texto: str, doc=None) -> List[Dict[str, Any]]:
    """
    Extrae nombres usando enfoque HÍBRIDO: Regex + spaCy.
    Acepta un parámetro opcional 'doc' para reutilizar un Doc ya procesado y evitar
    volver a llamar al pipeline de spaCy.
    """
    # Si no se proporciona un doc, cargar el pipeline y procesar
    if doc is None:
        nlp = _get_nlp()
        doc = nlp(texto)
    
    nombres_encontrados = []
    nombres_unicos = set()
    candidatos_regex = []
    
    # ========== FASE 1: CAPTURAR CANDIDATOS CON REGEX ==========
    print("\n[DEBUG] ===== FASE 1: CAPTURA DE CANDIDATOS CON REGEX =====")
    
    # Patrón mejorado: Captura nombres de 2-5 palabras (NO LISTAS)
    # Restricción: Mínimo 2 palabras, máximo 5 palabras
    # Patrón 1: Nombres en MAYÚSCULA COMPLETA (permite puntos, NO COMAS para evitar listas)
    # Captura: "SÁNCHEZ MARIÑO" o "GARCÍA LÓPEZ MARTÍN"
    patron_mayusculas = re.compile(
        r'\b([A-ZÁÉÍÓÚÑ]{2,}(?:[\s\.]+[A-ZÁÉÍÓÚÑ]{2,}){1,4})\b'
    )
    
    # Patrón 2: Nombres mixtos (Primera Letra Mayúscula + minúsculas, permite puntos, NO COMAS)
    # Captura: "Juan Pérez" o "María Andrea López"
    patron_mixto = re.compile(
        r'\b([A-ZÁÉÍÓÚÑ][a-záéíóúñ]{1,}(?:[\s\.]+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{1,}){1,4})\b'
    )
    
    # Capturar todos los candidatos de ambos patrones
    for match in patron_mayusculas.finditer(texto):
        candidatos_regex.append({
            "texto": match.group(1),
            "start": match.start(),
            "end": match.end(),
            "tipo_patron": "mayusculas"
        })
    
    for match in patron_mixto.finditer(texto):
        candidatos_regex.append({
            "texto": match.group(1),
            "start": match.start(),
            "end": match.end(),
            "tipo_patron": "mixto"
        })
    
    # Debug: Mostrar candidatos capturados por regex
    print(f"[DEBUG] Regex capturó {len(candidatos_regex)} candidatos:")
    for i, cand in enumerate(candidatos_regex[:15], 1):  # Mostrar máximo 15
        print(f"  {i}. '{cand['texto']}' (tipo: {cand['tipo_patron']}, pos: {cand['start']}-{cand['end']})")
    
    # ========== FASE 2: VALIDAR CANDIDATOS CON SPACY ==========
    print("\n[DEBUG] ===== FASE 2: VALIDACIÓN CON SPACY =====")
    
    print(f"[DEBUG] spaCy procesará {len(texto)} caracteres de texto")
    # Mostrar un resumen y también el texto completo normalizado que se le pasa a spaCy
    if len(texto) > 200:
        print(f"[DEBUG] Primeros 200 caracteres: {texto[:200]}...")
    else:
        print(f"[DEBUG] Texto completo (<=200 chars): {texto}")
    
    # Imprimir el texto NORMALIZADO completo que se pasa a spaCy (delimitado para facilitar copia)
    print("\n[DEBUG] --- TEXTO NORMALIZADO QUE SE PASA A SPACY (INICIO) ---")
    print(texto)
    print("[DEBUG] --- TEXTO NORMALIZADO QUE SE PASA A SPACY (FIN) ---\n")
 
    # El doc ya fue procesado por el llamador, usar sus entidades

    # Crear conjunto de spans validados por spaCy (entidades PER/PERSON)
    spans_validados = set()
    entidades_per_detectadas = []
    for ent in doc.ents:
        if ent.label_ in ("PER", "PERSON"):
            spans_validados.add((ent.start_char, ent.end_char))
            entidades_per_detectadas.append(ent.text)

    # Debug: Mostrar cuántas entidades PER detectó spaCy
    print(f"[DEBUG] spaCy detectó {len(entidades_per_detectadas)} entidades PER: {entidades_per_detectadas}")

    
    # Función auxiliar para verificar si hay anclas contextuales cerca
    def tiene_ancla_contextual(posicion: int, ventana: int = 100) -> tuple[bool, list]:
        start = max(0, posicion - ventana)
        end = min(len(texto), posicion + ventana)
        segmento = texto[start:end].lower()
        anclas_encontradas = [ancla for ancla in ANCLAS_CONTEXTUALES if ancla in segmento]
        return (len(anclas_encontradas) > 0, anclas_encontradas)
    
    # Procesar cada candidato regex
    print(f"\n[DEBUG] Procesando candidatos regex...")
    for candidato in candidatos_regex:
        nombre_raw = candidato["texto"]
        start_pos = candidato["start"]
        end_pos = candidato["end"]
        tipo_patron = candidato["tipo_patron"]

        # Como el regex YA NO captura comas (solo captura hasta 5 palabras sin comas),
        # no necesitamos separar por comas. Procesar el candidato directamente.
        
        # Limpiar puntuación del nombre (solo puntos) pero mantener espacios
        nombre_limpio_temp = re.sub(r'\.', ' ', nombre_raw)
        nombre_limpio_temp = re.sub(r'\s+', ' ', nombre_limpio_temp).strip()

        # NO eliminamos stop-words del nombre, solo las usamos para validar contexto
        tokens = nombre_limpio_temp.split()

        # Filtrar tokens que sean stop-words SOLO si están al inicio o final
        while tokens and tokens[0].lower() in STOP_WORDS:
            tokens.pop(0)
        while tokens and tokens[-1].lower() in STOP_WORDS:
            tokens.pop()

        # VALIDACIÓN ESTRICTA: mínimo 2, máximo 5 palabras
        if len(tokens) < 2:
            print(f"  ❌ '{nombre_raw}' rechazado: menos de 2 palabras ({len(tokens)})")
            continue
        
        if len(tokens) > 5:
            print(f"  ❌ '{nombre_raw}' rechazado: más de 5 palabras ({len(tokens)} palabras)")
            continue

        # Normalizar nombre final
        nombre_limpio = ' '.join(tokens)
        if tipo_patron == 'mayusculas':
            nombre_limpio = nombre_limpio.title()

        # Evitar duplicados
        if nombre_limpio.lower() in nombres_unicos:
            print(f"  ❌ '{nombre_raw}' rechazado: duplicado")
            continue

        # ========== VALIDACIÓN CON SPACY ==========
        # Verificar si este candidato se superpone con algún span validado por spaCy
        validado_por_spacy = False
        span_coincidente = None
        for span_start, span_end in spans_validados:
            # Hay superposición si los rangos se cruzan
            if not (end_pos <= span_start or start_pos >= span_end):
                validado_por_spacy = True
                span_coincidente = (span_start, span_end)
                break

        # Si no fue validado por spaCy, verificar si tiene anclas contextuales
        if not validado_por_spacy:
            tiene_ancla, anclas_encontradas = tiene_ancla_contextual(start_pos)

            # Debug: Mostrar el contexto cercano
            ctx_start = max(0, start_pos - 100)
            ctx_end = min(len(texto), end_pos + 100)
            contexto_debug = texto[ctx_start:ctx_end]

            if tiene_ancla:
                print(f"  ✅ '{nombre_raw}' validado por ANCLA CONTEXTUAL: {anclas_encontradas}")
                print(f"     Contexto: ...{contexto_debug[:80]}...")
                validado_por_spacy = True
            else:
                print(f"  ❌ '{nombre_raw}' rechazado: NO validado por spaCy ni ancla contextual")
                print(f"     Contexto: ...{contexto_debug[:80]}...")
                print(f"     Anclas buscadas en ventana ±100 chars: {ANCLAS_CONTEXTUALES}")
                continue
        else:
            print(f"  ✅ '{nombre_raw}' validado por SPACY (span: {span_coincidente})")

        nombres_unicos.add(nombre_limpio.lower())

        # Extraer contexto
        start_ctx = max(0, start_pos - 60)
        end_ctx = min(len(texto), end_pos + 60)
        contexto = texto[start_ctx:end_ctx].strip()

        nombres_encontrados.append({
            "nombre": nombre_limpio,
            "contexto": contexto,
            "posicion": start_pos
        })

    # Debug: Resumen final
    print(f"\n[DEBUG] Resumen:")
    print(f"  - Candidatos regex capturados: {len(candidatos_regex)}")
    print(f"  - Validados por spaCy o contexto: {len(nombres_encontrados)}")
    print(f"  - Nombres únicos finales: {[n['nombre'] for n in nombres_encontrados]}")
    
    # Ordenar por posición
    nombres_encontrados.sort(key=lambda x: x['posicion'])
    
    # Eliminar campo posición
    for nombre in nombres_encontrados:
        del nombre['posicion']
    
    return nombres_encontrados


def _extraer_y_validar_documento(texto: str, tipo_doc: str) -> List[Dict[str, any]]:
    """
    Extrae y valida números de documento según normativas argentinas.
    
    Validaciones aplicadas:
    - DNI: 7-8 dígitos
    - CUIL: 11 dígitos, prefijos 20/23/24/27, dígito verificador
    - CUIT: 11 dígitos, prefijos 20-27/30/33-34, dígito verificador
    - CUIF: 1-10 dígitos numéricos
    - Matrícula: 1-10 caracteres alfanuméricos
    
    Args:
        texto: Texto normalizado donde buscar
        tipo_doc: Tipo de documento (dni, matricula, cuif, cuit, cuil)
        
    Returns:
        Lista con documentos encontrados y validados:
        [
            {
                "numero": "44667656",
                "contexto": "..."
            }
        ]
    """
    documentos_encontrados = []
    numeros_unicos = set()
    
    tipo_doc_upper = tipo_doc.upper()
    patron = PATRONES_DOCUMENTOS[tipo_doc_upper]
    regex = re.compile(patron, flags=re.IGNORECASE)
    
    # Mapa de validadores
    validadores = {
        "dni": validar_dni,
        "cuil": validar_cuil,
        "cuit": validar_cuit,
        "cuif": validar_cuif,
        "matricula": validar_matricula
    }
    
    validador = validadores.get(tipo_doc)
    
    for match in regex.finditer(texto):
        numero = match.group(1)
        
        # Limpiar número (sin separadores)
        numero_limpio = re.sub(r'\D', '', numero) if tipo_doc in ("cuit", "cuil", "dni", "cuif") else numero
        
        # Evitar duplicados
        if numero_limpio in numeros_unicos:
            continue
        
        # Validar formato
        es_valido = validador(numero_limpio) if validador else False
        
        # Solo agregar si es válido
        if not es_valido:
            continue
        
        numeros_unicos.add(numero_limpio)
        
        # Extraer contexto
        start_ctx = max(0, match.start() - 60)
        end_ctx = min(len(texto), match.end() + 60)
        contexto = texto[start_ctx:end_ctx].strip()
        
        documento = {
            "numero": numero_limpio,
            "contexto": contexto
        }
        
        documentos_encontrados.append(documento)
    
    return documentos_encontrados


def validar_entidades_solicitadas(entidades: List[str]) -> tuple[bool, Optional[str]]:
    """
    Valida que las entidades solicitadas sean válidas.
    
    Args:
        entidades: Lista de entidades a validar
        
    Returns:
        Tupla (es_valido, mensaje_error)
    """
    if not entidades or len(entidades) == 0:
        return False, "Debe especificar al menos una entidad a extraer"
    
    entidades_validas = {"nombre", "nombres", "dni", "matricula", "cuif", "cuit", "cuil"}
    entidades_invalidas = set(e.lower().strip() for e in entidades) - entidades_validas
    
    if entidades_invalidas:
        return False, (
            f"Entidades no válidas: {', '.join(entidades_invalidas)}. "
            f"Entidades válidas: nombre (personas), dni (7-8 dígitos), "
            f"matricula (alfanumérico 1-10 chars), cuif (1-10 dígitos), "
            f"cuit (11 dígitos, prefijos 20-27/30/33-34), cuil (11 dígitos, prefijos 20/23-24/27)"
        )
    return True, None
