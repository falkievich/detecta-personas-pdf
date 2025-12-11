"""
Módulo para extraer entidades específicas de un PDF usando spaCy.
Soporta extracción de nombres (6 fases) y documentos (DNI, CUIL, CUIT, CUIF, Matrícula).
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
from funcs.nlp_extractors.constantes import PATRONES_DOCUMENTOS, STOP_WORDS, PALABRAS_FILTRO_NOMBRES
from funcs.nlp_extractors.validadores_entidades import (
    validar_dni, validar_cuil, validar_cuit, 
    validar_cuif, validar_matricula, validar_cbu
)
from funcs.nlp_extractors.contextual_anchor_rules import ContextualAnchorMatcher


# Patrones regex precompilados para extracción de nombres
PATRON_MAYUSCULAS = re.compile(r'\b([A-ZÁÉÍÓÚÑ]{2,}(?:[\s\.]+[A-ZÁÉÍÓÚÑ]{2,}){1,4})\b')
PATRON_MIXTO = re.compile(r'\b([A-ZÁÉÍÓÚÑ][a-záéíóúñ]{1,}(?:[\s\.]+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{1,}){1,4})\b')
PATRON_COMA = re.compile(r'\b([A-ZÁÉÍÓÚÑ]{2,}(?:\s+[A-ZÁÉÍÓÚÑ]{2,}){0,2},\s+[A-ZÁÉÍÓÚÑ]{2,}(?:\s+[A-ZÁÉÍÓÚÑ]{2,}){0,2})\b')

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


def _extraer_contexto(texto: str, start: int, end: int, window: int = 60) -> str:
    """
    Extrae el contexto alrededor de una posición en el texto.
    
    Args:
        texto: Texto completo
        start: Posición inicial de la entidad
        end: Posición final de la entidad
        window: Ventana de contexto (caracteres antes y después)
        
    Returns:
        Contexto extraído
    """
    start_ctx = max(0, start - window)
    end_ctx = min(len(texto), end + window)
    return texto[start_ctx:end_ctx].strip()


def _limpiar_y_normalizar_nombre(nombre_raw: str, tipo_patron: str) -> tuple[list[str], str]:
    """
    Limpia y normaliza un nombre capturado por regex.
    
    Args:
        nombre_raw: Nombre original capturado
        tipo_patron: Tipo de patrón ("mayusculas", "mixto", "coma")
        
    Returns:
        Tupla (tokens_limpios, nombre_normalizado)
    """
    # Limpiar puntuación del nombre
    if tipo_patron == "coma":
        # "CARBALLO, MARTA" → "CARBALLO MARTA"
        nombre_limpio_temp = re.sub(r',', ' ', nombre_raw)
        nombre_limpio_temp = re.sub(r'\s+', ' ', nombre_limpio_temp).strip()
    else:
        # Para otros patrones, solo limpiar puntos
        nombre_limpio_temp = re.sub(r'\.', ' ', nombre_raw)
        nombre_limpio_temp = re.sub(r'\s+', ' ', nombre_limpio_temp).strip()

    # Filtrar stop-words al inicio/final
    tokens = nombre_limpio_temp.split()
    while tokens and tokens[0].lower() in STOP_WORDS:
        tokens.pop(0)
    while tokens and tokens[-1].lower() in STOP_WORDS:
        tokens.pop()

    # Normalizar nombre final
    nombre_limpio = ' '.join(tokens)
    if tipo_patron == 'mayusculas':
        nombre_limpio = nombre_limpio.title()
    
    return tokens, nombre_limpio



def extraer_entidades_especificas(
    entidades_solicitadas: List[str],
    path_pdf: Optional[str] = None,
    raw_text: Optional[str] = None,
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
    Extrae entidades específicas de un PDF o texto según lo solicitado.
    IMPORTANTE: Usa dos versiones del texto:
    - texto_crudo: para spaCy NER (nombres)
    - texto_normalizado: para documentos (DNI, CUIT, etc.)
    
    Args:
        entidades_solicitadas: Lista de entidades a extraer
        path_pdf: Ruta al archivo PDF (opcional si se proporciona raw_text)
        raw_text: Texto plano a analizar (opcional si se proporciona path_pdf)
    """
    # Validar entrada
    if not path_pdf and not raw_text:
        raise ValueError("Se debe pasar path_pdf o raw_text")
    
    if path_pdf and raw_text:
        raise ValueError("Solo se puede pasar path_pdf O raw_text, no ambos")
    
    # Normalizar entidades solicitadas
    entidades_solicitadas = [e.lower().strip() for e in entidades_solicitadas]
    
    # Validar entidades
    entidades_validas = {"nombre", "nombres", "dni", "matricula", "cuif", "cuit", "cuil", "cbu"}
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
    # Extraer texto NORMALIZADO para todo el flujo
    # print("[DEBUG] Extrayendo texto NORMALIZADO...")
    
    if path_pdf:
        # Caso 1: Desde PDF
        texto_normalizado = normalizacion_avanzada_pdf(path_pdf=path_pdf)
    else:
        # Caso 2: Desde texto plano
        texto_normalizado = normalizacion_avanzada_pdf(raw_text=raw_text)
    
    # print(f"[DEBUG] Texto NORMALIZADO extraído: {len(texto_normalizado)} caracteres")
    
    # Imprimir el texto normalizado completo SIEMPRE (independiente de las entidades solicitadas)
    # print("[DEBUG] --- TEXTO NORMALIZADO COMPLETO (INICIO) ---")
    # print(texto_normalizado)
    # print("[DEBUG] --- TEXTO NORMALIZADO COMPLETO (FIN) ---")
    
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
        # print("[DEBUG] Procesando texto con spaCy para extracción de nombres...")
        nlp = _get_nlp()
        doc = nlp(texto_crudo)  # ← SIEMPRE texto_crudo
    
    # Estructura de resultado
    resultado: Dict[str, List[Dict[str, Any]]] = {}
    
    # Extracción de nombres (usa texto crudo)
    if "nombre" in entidades_solicitadas:
        # print("[DEBUG] Extrayendo NOMBRES con texto CRUDO...")
        resultado["nombres"] = _extraer_nombres_con_contexto(texto_crudo, doc=doc)
        # print(f"[DEBUG] Nombres encontrados: {len(resultado['nombres'])}")
    
    # Extracción de documentos (usa texto normalizado)
    for entidad in entidades_solicitadas:
        if entidad == "nombre":
            continue  # Ya procesado arriba
            
        entidad_key = entidad.upper()
        if entidad_key in PATRONES_DOCUMENTOS:
            # print(f"[DEBUG] Extrayendo {entidad_key} con texto NORMALIZADO...")
            resultado[entidad] = _extraer_y_validar_documento(
                texto_normalizado,  # ← TEXTO NORMALIZADO
                entidad
            )
            # print(f"[DEBUG] {entidad_key} encontrados: {len(resultado[entidad])}")

    # Generar visualización: respetar parámetro explícito si se pasó, sino usar config global
    debe_visualizar = False
    if visualizar is not None:
        debe_visualizar = bool(visualizar)
    else:
        debe_visualizar = _VIS_DISPONIBLE and is_visualization_enabled()
    
    if debe_visualizar and doc is not None:
        # Generar visualización pero NO incluir el HTML ni rutas en la respuesta API
        # print("[DEBUG] Generando visualización con displaCy (no incluida en la respuesta)...")
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
            # print(f"[DEBUG] Error al generar visualización (se ignorará): {e}")
            pass

    return resultado


def _extraer_nombres_con_contexto(texto: str, doc=None) -> List[Dict[str, Any]]:
    """
    Extrae nombres usando enfoque HÍBRIDO MEJORADO en 6 fases:
    
    Fase 1: Regex - Captura patrones de nombres (mayúsculas/mixtos)
    Fase 2: spaCy NER - Valida con entidades PER/PERSON
    Fase 3: Reglas Contextuales - Aplica 6 reglas especializadas:
        1. ANCLAS_CONTEXTUALES: Detecta cerca de palabras-cue
        2. NOMBRE_DESPUES_DE_CONTRA: Detecta después de "contra"
        3. PATRON_C_S: Detecta entre "C/" y "S/"
        4. APELLIDO_NOMBRE_JUDICIAL: Detecta formato Title Case
        5. NOMBRE_ANTES_DE_C_BARRA: Detecta antes de "C/" (demandante)
        6. NOMBRE_JUDICIAL_CON_COMA: Detecta formato "APELLIDO, NOMBRE"
    Fase 4: Limpieza de Anclas - Elimina palabras-cue contextuales:
        - Remueve "señor", "doctor", "dni", etc. de los nombres detectados
        - Mantiene solo los tokens que son parte del nombre real
    Fase 5: Deduplicación y Limpieza de Bordes:
        - Paso 5.1: Elimina duplicados con tokens en diferente orden
        - Paso 5.1: Elimina subconjuntos (nombres cortos contenidos en nombres largos)
        - Paso 5.2: Limpia preposiciones/conjunciones al inicio/final ("en", "del", "y", etc.)
    Fase 6: Filtro de Palabras - Elimina nombres con palabras institucionales/jurídicas:
        - Rechaza nombres que contienen: "expediente", "ley", "constitución", etc.
        - Comparación case-insensitive: "Ley" = "LEY" = "ley"
    
    Args:
        texto: Texto normalizado a procesar
        doc: Documento spaCy ya procesado (opcional, para reutilizar)
        
    Returns:
        Lista de nombres únicos con contexto
    """
    # Si no se proporciona un doc, cargar el pipeline y procesar
    if doc is None:
        nlp = _get_nlp()
        doc = nlp(texto)
    else:
        nlp = _get_nlp()
    
    nombres_encontrados = []
    nombres_unicos = set()
    candidatos_regex = []
    candidatos_rechazados_spacy = []  # Almacena candidatos rechazados por spaCy para validar con reglas
    
    # ========== FASE 1: CAPTURAR CANDIDATOS CON REGEX ==========
    # print("\n[DEBUG] ===== FASE 1: CAPTURA DE CANDIDATOS CON REGEX =====")
    
    # Capturar todos los candidatos de los tres patrones precompilados
    for match in PATRON_MAYUSCULAS.finditer(texto):
        candidatos_regex.append({
            "texto": match.group(1),
            "start": match.start(),
            "end": match.end(),
            "tipo_patron": "mayusculas"
        })
    
    for match in PATRON_MIXTO.finditer(texto):
        candidatos_regex.append({
            "texto": match.group(1),
            "start": match.start(),
            "end": match.end(),
            "tipo_patron": "mixto"
        })
    
    for match in PATRON_COMA.finditer(texto):
        candidatos_regex.append({
            "texto": match.group(1),
            "start": match.start(),
            "end": match.end(),
            "tipo_patron": "coma"
        })
    
    # Debug: Mostrar candidatos capturados por regex
    # print(f"[DEBUG] Regex capturó {len(candidatos_regex)} candidatos:")
    for i, cand in enumerate(candidatos_regex[:15], 1):  # Mostrar máximo 15
        # print(f"  {i}. '{cand['texto']}' (tipo: {cand['tipo_patron']}, pos: {cand['start']}-{cand['end']})")
        pass
    
    # FASE 2: Validar candidatos con spaCy
    # print("\n[DEBUG] ===== FASE 2: VALIDACIÓN CON SPACY =====")
    # print(f"[DEBUG] spaCy procesará {len(texto)} caracteres de texto")
    
    spans_validados = set()
    entidades_per_detectadas = []
    for ent in doc.ents:
        if ent.label_ in ("PER", "PERSON"):
            spans_validados.add((ent.start_char, ent.end_char))
            entidades_per_detectadas.append(ent.text)
    
    # print(f"[DEBUG] spaCy detectó {len(entidades_per_detectadas)} entidades PER: {entidades_per_detectadas}")

    
    # Procesar cada candidato regex
    # print(f"\n[DEBUG] Procesando candidatos regex...")
    for candidato in candidatos_regex:
        nombre_raw = candidato["texto"]
        start_pos = candidato["start"]
        end_pos = candidato["end"]
        tipo_patron = candidato["tipo_patron"]

        # Limpiar y normalizar usando función auxiliar
        tokens, nombre_limpio = _limpiar_y_normalizar_nombre(nombre_raw, tipo_patron)

        # VALIDACIÓN ESTRICTA: mínimo 2, máximo 5 palabras
        if len(tokens) < 2:
            # print(f"  ❌ '{nombre_raw}' rechazado: menos de 2 palabras")
            continue
        
        if len(tokens) > 5:
            # print(f"  ❌ '{nombre_raw}' rechazado: más de 5 palabras")
            continue

        # Validar que todos los tokens tengan al menos 2 caracteres
        if not _tiene_tokens_validos(nombre_limpio, min_longitud=2):
            # print(f"  ❌ '{nombre_raw}' rechazado: contiene tokens de 1 carácter")
            continue

        # Evitar duplicados
        if nombre_limpio.lower() in nombres_unicos:
            # print(f"  ❌ '{nombre_raw}' rechazado: duplicado")
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

        # Si no fue validado por spaCy, guardar para validar con reglas contextuales (Fase 3)
        if not validado_por_spacy:
            # print(f"  ⚠️  '{nombre_raw}' NO validado por spaCy NER → se validará con reglas contextuales")
            
            # Guardar candidato rechazado para validación posterior con reglas
            candidatos_rechazados_spacy.append({
                "nombre": nombre_limpio,
                "start": start_pos,
                "end": end_pos
            })
            continue
        else:
            # print(f"  ✅ '{nombre_raw}' validado por SPACY (span: {span_coincidente})")
            pass

        nombres_unicos.add(nombre_limpio.lower())

        # Extraer contexto usando función centralizada
        contexto = _extraer_contexto(texto, start_pos, end_pos, window=60)

        nombres_encontrados.append({
            "nombre": nombre_limpio,
            "contexto": contexto,
            "posicion": start_pos
        })

    # FASE 3: Aplicar reglas contextuales
    # print("\n[DEBUG] ===== FASE 3: DETECCIÓN CON REGLAS CONTEXTUALES =====")
    
    context_matcher = ContextualAnchorMatcher(nlp)
    context_matcher.add_default_rules()
    matches_contextuales = context_matcher.find_matches(doc)
    
    # print(f"[DEBUG] Reglas contextuales detectaron {len(matches_contextuales)} coincidencias")
    conteo_por_regla = {}
    for match in matches_contextuales:
        regla = match.get("rule", "unknown")
        conteo_por_regla[regla] = conteo_por_regla.get(regla, 0) + 1
    
    # print(f"[DEBUG] Desglose por regla:")
    for regla, count in conteo_por_regla.items():
        # print(f"  - {regla}: {count} coincidencias")
        pass
    
    # Crear conjuntos para validación de candidatos rechazados
    spans_reglas_contextuales = set()
    nombres_reglas_contextuales = set()  # Nombres detectados por reglas (normalizados)
    
    for match in matches_contextuales:
        spans_reglas_contextuales.add((match["span_start"], match["span_end"]))
        # Normalizar y guardar tokens del nombre para comparación flexible
        nombre_normalizado = " ".join(match["name_tokens"]).lower()
        nombres_reglas_contextuales.add(nombre_normalizado)
    
    # Procesar coincidencias de reglas contextuales
    for match in matches_contextuales:
        # Usar nombre_original si está disponible (preserva formato judicial con coma)
        # De lo contrario, unir tokens normalmente
        if "nombre_original" in match:
            nombre_raw = match["nombre_original"]
            nombre_limpio = nombre_raw  # Preservar tal cual (ej: "CARBALLO, MARTA")
        else:
            nombre_raw = " ".join(match["name_tokens"])
            nombre_limpio = nombre_raw.title()
        
        # Verificar si ya fue agregado
        if nombre_limpio.lower() in nombres_unicos:
            # print(f"  ⚠️  '{nombre_raw}' (regla: {match.get('rule', 'unknown')}, ancla: {match['anchor']}) ya detectado previamente")
            continue
        
        # Agregar nombre detectado por regla contextual
        nombres_unicos.add(nombre_limpio.lower())
        
        # Validar que todos los tokens tengan al menos 2 caracteres
        if not _tiene_tokens_validos(nombre_limpio, min_longitud=2):
            # print(f"  ❌ '{nombre_raw}' rechazado: contiene tokens de 1 carácter")
            continue
        
        # print(f"  ✅ '{nombre_raw}' detectado por {match.get('rule', 'REGLA_DESCONOCIDA')} (ancla: {match['anchor']})")
        
        nombres_encontrados.append({
            "nombre": nombre_limpio,
            "contexto": match["context"],
            "posicion": match["span_start"]
        })
    
    # ========== VALIDAR CANDIDATOS RECHAZADOS POR SPACY CON REGLAS CONTEXTUALES ==========
    # print(f"\n[DEBUG] Validando {len(candidatos_rechazados_spacy)} candidatos rechazados por spaCy...")
    
    for candidato in candidatos_rechazados_spacy:
        nombre = candidato["nombre"]
        start_pos = candidato["start"]
        end_pos = candidato["end"]
        
        validado_por_regla = False
        metodo_validacion = None
        
        # Método 1: Verificar superposición de spans (posiciones)
        for span_start, span_end in spans_reglas_contextuales:
            # Hay superposición si los rangos se cruzan
            if not (end_pos <= span_start or start_pos >= span_end):
                validado_por_regla = True
                metodo_validacion = "superposición de spans"
                break
        
        # Método 2: Verificar si los tokens del candidato están contenidos en algún nombre de regla
        if not validado_por_regla:
            tokens_candidato = set(nombre.lower().split())
            for nombre_regla in nombres_reglas_contextuales:
                tokens_regla = set(nombre_regla.split())
                # Si todos los tokens del candidato están en la regla, o viceversa
                if tokens_candidato.issubset(tokens_regla) or tokens_regla.issubset(tokens_candidato):
                    validado_por_regla = True
                    metodo_validacion = "coincidencia de tokens"
                    break
        
        # Método 3: Verificar si el nombre del candidato contiene o está contenido en algún nombre de regla
        if not validado_por_regla:
            nombre_lower = nombre.lower()
            for nombre_regla in nombres_reglas_contextuales:
                if nombre_lower in nombre_regla or nombre_regla in nombre_lower:
                    validado_por_regla = True
                    metodo_validacion = "subcadena de texto"
                    break
        
        if validado_por_regla:
            # Validar que todos los tokens tengan al menos 2 caracteres
            if not _tiene_tokens_validos(nombre, min_longitud=2):
                # print(f"  ❌ '{nombre}' rechazado: contiene tokens de 1 carácter (ej: 'S E N T E N')")
                continue
            
            # Verificar si ya fue agregado
            if nombre.lower() in nombres_unicos:
                # print(f"  ⚠️  '{nombre}' ya fue agregado por las reglas contextuales")
                continue
            
            # Agregar nombre rescatado por reglas contextuales
            nombres_unicos.add(nombre.lower())
            
            # Extraer contexto usando función centralizada
            contexto = _extraer_contexto(texto, start_pos, end_pos, window=60)
            
            # print(f"  ✅ '{nombre}' RESCATADO por regla contextual ({metodo_validacion})")
            
            nombres_encontrados.append({
                "nombre": nombre,
                "contexto": contexto,
                "posicion": start_pos
            })
        else:
            # print(f"  ❌ '{nombre}' rechazado definitivamente (no validado ni por spaCy ni por reglas)")
            pass
    
    # FASE 4: Limpieza de anclas contextuales
    # print("\n[DEBUG] ===== FASE 4: LIMPIEZA DE ANCLAS CONTEXTUALES =====")
    # print(f"[DEBUG] Nombres antes de limpiar anclas: {len(nombres_encontrados)}")
    nombres_sin_anclas = _limpiar_anclas_de_nombres(nombres_encontrados)
    # print(f"[DEBUG] Nombres después de limpiar anclas: {len(nombres_sin_anclas)}")
    
    # FASE 5: Deduplicación y limpieza de bordes
    # print("\n[DEBUG] ===== FASE 5: DEDUPLICACIÓN Y LIMPIEZA DE BORDES =====")
    # print(f"[DEBUG] Nombres antes de deduplicación: {len(nombres_sin_anclas)}")
    nombres_deduplicados = _eliminar_duplicados_y_subconjuntos(nombres_sin_anclas)
    # print(f"[DEBUG] Nombres después de deduplicación: {len(nombres_deduplicados)}")
    
    nombres_limpios = _limpiar_bordes_de_nombres(nombres_deduplicados)
    # print(f"[DEBUG] Nombres después de limpiar bordes: {len(nombres_limpios)}")
    
    # FASE 6: Filtrar palabras no-nombres
    # print("\n[DEBUG] ===== FASE 6: FILTRO DE PALABRAS NO-NOMBRES =====")
    # print(f"[DEBUG] Nombres antes de filtrar palabras: {len(nombres_limpios)}")
    nombres_finales = _filtrar_palabras_no_nombres(nombres_limpios)
    # print(f"[DEBUG] Nombres después de filtrar palabras: {len(nombres_finales)}")
    
    # Debug: Resumen final
    # print(f"\n[DEBUG] ===== RESUMEN FINAL =====")
    # print(f"  - Fase 1 - Candidatos regex capturados: {len(candidatos_regex)}")
    # print(f"  - Fase 3 - Detectados por reglas contextuales: {len(matches_contextuales)}")
    # print(f"  - Fase 4 - Nombres después de limpiar anclas: {len(nombres_sin_anclas)}")
    # print(f"  - Fase 5 - Nombres después de deduplicación: {len(nombres_limpios)}")
    # print(f"  - Fase 6 - Nombres después de filtrar palabras: {len(nombres_finales)}")
    # print(f"  - TOTAL nombres únicos finales: {len(nombres_finales)}")
    lista_nombres_finales = [n['nombre'] for n in nombres_finales]
    # print(f"  - Lista final: {lista_nombres_finales}")
    
    # Ordenar por posición
    nombres_finales.sort(key=lambda x: x['posicion'])
    
    # Eliminar campo posición
    for nombre in nombres_finales:
        del nombre['posicion']
    
    return nombres_finales


def _filtrar_palabras_no_nombres(nombres: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    FASE 6: Filtra nombres que contienen palabras que NO son nombres de persona.
    
    Esta es la última fase de filtrado y se aplica después de toda la validación,
    deduplicación y limpieza. Rechaza nombres que contienen palabras institucionales,
    jurídicas o geográficas que indican que NO es un nombre de persona.
    
    Ejemplos de lo que filtra:
        - "Expediente Nacional" → contiene "expediente"
        - "Constitución Provincial" → contiene "constitución" y "provincial"
        - "Ley Suprema" → contiene "ley" (case-insensitive)
        - "Buenos Aires" → contiene "buenos" y "aires"
    
    La comparación es case-insensitive: "Ley", "LEY", "ley" se consideran iguales.
    
    Args:
        nombres: Lista de diccionarios con 'nombre', 'contexto', 'posicion'
        
    Returns:
        Lista filtrada sin nombres que contengan palabras filtro
    """
    nombres_validos = []
    
    for item in nombres:
        nombre_original = item['nombre']
        tokens = nombre_original.split()
        
        # Convertir tokens a minúsculas para comparación case-insensitive
        tokens_lower = [t.lower() for t in tokens]
        
        # Buscar si algún token está en PALABRAS_FILTRO_NOMBRES
        palabras_encontradas = [t for t in tokens_lower if t in PALABRAS_FILTRO_NOMBRES]
        
        if palabras_encontradas:
            # print(f"  ❌ '{nombre_original}' filtrado: contiene palabras no-nombre ({', '.join(palabras_encontradas)})")
            pass
        else:
            nombres_validos.append(item)
    
    return nombres_validos


def _limpiar_anclas_de_nombres(nombres: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    FASE 4: Limpia las ANCLAS_CONTEXTUALES de los nombres detectados.
    
    Proceso:
    - Elimina palabras-cue contextuales ("señor", "doctor", "dni", etc.)
    - NO elimina preposiciones en bordes (eso se hace en Fase 5 después de deduplicación)
    
    Ejemplos:
        "Señor Juez Vanina Marisol Garcia Dni" → "Vanina Marisol Garcia"
        "Doctor Carlos Pérez" → "Carlos Pérez"
        "Sr Juan García DNI" → "Juan García"
    
    Args:
        nombres: Lista de diccionarios con 'nombre', 'contexto', 'posicion'
        
    Returns:
        Lista con nombres limpios (sin anclas contextuales)
    """
    from funcs.nlp_extractors.constantes import ANCLAS_CONTEXTUALES
    
    nombres_limpios = []
    
    for item in nombres:
        nombre_original = item['nombre']
        tokens = nombre_original.split()
        
        # Filtrar tokens que sean anclas contextuales (comparación case-insensitive)
        tokens_limpios = []
        for token in tokens:
            token_lower = token.lower()
            # Remover puntos para comparar (ej: "Dr." → "dr")
            token_sin_punto = token_lower.rstrip('.')
            
            # Verificar si el token es un ancla contextual
            if token_lower not in ANCLAS_CONTEXTUALES and token_sin_punto not in ANCLAS_CONTEXTUALES:
                tokens_limpios.append(token)
        
        # Reconstruir nombre sin anclas
        nombre_sin_anclas = ' '.join(tokens_limpios).strip()
        
        # Validar que queden al menos 2 tokens (nombre válido)
        tokens_finales = nombre_sin_anclas.split()
        if len(tokens_finales) >= 2:
            if nombre_sin_anclas != nombre_original:
                # print(f"  🧹 '{nombre_original}' → '{nombre_sin_anclas}' (anclas limpiadas)")
                pass
            
            nombres_limpios.append({
                'nombre': nombre_sin_anclas,
                'contexto': item['contexto'],
                'posicion': item['posicion']
            })
        else:
            # print(f"  ❌ '{nombre_original}' descartado: menos de 2 tokens después de limpiar anclas")
            pass
    
    return nombres_limpios


def _limpiar_bordes_de_nombres(nombres: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    FASE 5.2: Limpia preposiciones y conjunciones del inicio y final de nombres.
    
    Esta función se aplica DESPUÉS de la deduplicación para asegurar que
    los nombres finales no tengan palabras como "en", "del", "de", "y" al inicio/final.
    
    Ejemplos:
        "En Vallejos Margarita Beatriz" → "Vallejos Margarita Beatriz"
        "Del Rene Antonio Quer" → "Rene Antonio Quer"
        "Y Bianca Giovanna Muller" → "Bianca Giovanna Muller"
        "Maria De Los Angeles Y" → "Maria De Los Angeles"
        "Lopez Gonzales y Perez" → "Lopez Gonzales y Perez" (NO cambia, "y" está en medio)
    
    Args:
        nombres: Lista de diccionarios con 'nombre', 'contexto', 'posicion'
        
    Returns:
        Lista con nombres con bordes limpios
    """
    from funcs.nlp_extractors.constantes import limpiar_bordes_nombre
    
    nombres_limpios = []
    
    for item in nombres:
        nombre_original = item['nombre']
        nombre_limpio = limpiar_bordes_nombre(nombre_original)
        
        # Validar que queden al menos 2 tokens después de limpiar bordes
        tokens_finales = nombre_limpio.split()
        if len(tokens_finales) >= 2:
            if nombre_limpio != nombre_original:
                # print(f"  🧹 '{nombre_original}' → '{nombre_limpio}' (bordes limpiados)")
                pass
            
            nombres_limpios.append({
                'nombre': nombre_limpio,
                'contexto': item['contexto'],
                'posicion': item['posicion']
            })
        else:
            # print(f"  ❌ '{nombre_original}' descartado: menos de 2 tokens después de limpiar bordes")
            pass
    
    return nombres_limpios


def _es_nombre_valido_sin_palabras_prohibidas(nombre: str) -> bool:
    """
    Verifica si un nombre NO contiene palabras prohibidas (institucionales, jurídicas, etc.).
    
    Esta función se usa ANTES de eliminar subconjuntos para evitar que nombres
    "tóxicos" (con palabras prohibidas) eliminen a nombres válidos más cortos.
    
    Ejemplo:
        "CARLOS PICCIOCHI RIOS" → True (válido)
        "CARLOS PICCIOCHI RIOS Secretario Cámara" → False (contiene "secretario" y "cámara")
    
    Args:
        nombre: Nombre a validar
        
    Returns:
        True si el nombre NO contiene palabras prohibidas, False en caso contrario
    """
    from funcs.nlp_extractors.constantes import PALABRAS_FILTRO_NOMBRES
    
    tokens = set(nombre.lower().split())
    # Si tiene intersección con palabras filtro, es inválido
    if tokens.intersection(PALABRAS_FILTRO_NOMBRES):
        return False
    return True


def _tiene_tokens_validos(nombre: str, min_longitud: int = 2) -> bool:
    """
    Verifica que todos los tokens del nombre tengan al menos una longitud mínima.
    
    Esta función previene la detección de letras sueltas como nombres:
    - "S E N T E N C I A" (cada token tiene 1 char) → False
    - "Carlos Picciochi" (tokens de 6 y 9 chars) → True
    
    Args:
        nombre: Nombre a validar
        min_longitud: Longitud mínima requerida para cada token (default: 2)
        
    Returns:
        True si todos los tokens tienen al menos min_longitud caracteres, False en caso contrario
    """
    tokens = nombre.split()
    
    # Validar que todos los tokens tengan al menos min_longitud caracteres
    for token in tokens:
        if len(token) < min_longitud:
            return False
    
    return True


def _eliminar_duplicados_y_subconjuntos(nombres: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Elimina duplicados y subconjuntos de nombres CON VALIDACIÓN INTELIGENTE.
    
    **CAMBIO IMPORTANTE (Solución al problema de "Superconjunto Tóxico"):**
    Solo permite que un nombre largo elimine a un nombre corto si el nombre largo
    también es VÁLIDO (no contiene palabras prohibidas).
    
    Casos que maneja:
    1. Duplicados con tokens en diferente orden:
       - "Gómez Sara Antonia" vs "Sara Antonia Gómez" → Elimina uno
    
    2. Subconjuntos SOLO SI EL SUPERCONJUNTO ES VÁLIDO:
       - "Carlos Rios" ⊂ "Carlos Rios Secretario" (inválido) → MANTIENE ambos (el corto sobrevive)
       - "Carlos Rios" ⊂ "Carlos Maria Rios" (válido) → ELIMINA el corto (el largo lo absorbe)
    
    Ejemplo del problema resuelto:
        Antes: "CARLOS PICCIOCHI RIOS" era eliminado por "CARLOS... Secretario Cámara",
               luego el largo era filtrado → resultado: ninguno.
        Ahora: "CARLOS PICCIOCHI RIOS" NO es eliminado porque el superconjunto tiene
               palabras prohibidas → resultado: "CARLOS PICCIOCHI RIOS" sobrevive.
    
    Args:
        nombres: Lista de diccionarios con 'nombre', 'contexto', 'posicion'
        
    Returns:
        Lista filtrada sin duplicados ni subconjuntos (con lógica inteligente)
    """
    if not nombres:
        return []
    
    # Convertir cada nombre a conjunto de tokens (en minúsculas para comparación)
    nombres_con_tokens = []
    for item in nombres:
        tokens = set(item['nombre'].lower().split())
        nombres_con_tokens.append({
            'original': item,
            'tokens': tokens,
            'tokens_count': len(tokens),
            'es_valido': _es_nombre_valido_sin_palabras_prohibidas(item['nombre'])
        })
    
    # Ordenar por cantidad de tokens (ASCENDENTE) para procesar primero los más cortos
    # Esto permite que los cortos se agreguen primero si son válidos
    nombres_con_tokens.sort(key=lambda x: x['tokens_count'])
    
    nombres_validos = []
    tokens_ya_usados = []
    
    for item in nombres_con_tokens:
        tokens_actual = item['tokens']
        nombre_actual = item['original']['nombre']
        es_actual_valido = item['es_valido']
        es_valido = True
        
        # Si el nombre actual tiene palabras prohibidas, descartarlo de inmediato
        if not es_actual_valido:
            # print(f"  🗑️  '{nombre_actual}' eliminado: contiene palabras prohibidas (pre-filtro)")
            continue
        
        # Verificar contra todos los nombres ya agregados
        for idx, tokens_existente in enumerate(tokens_ya_usados):
            nombre_existente = nombres_validos[idx]['nombre']
            
            # CASO 1: Duplicado con tokens en diferente orden
            # Si los conjuntos de tokens son idénticos → es duplicado
            if tokens_actual == tokens_existente:
                # print(f"  🗑️  '{nombre_actual}' eliminado: duplicado con diferente orden")
                es_valido = False
                break
            
            # CASO 2: El actual es subconjunto de uno existente
            # Si el existente ya está en la lista, significa que era válido
            # Por lo tanto, el actual (más corto) debe ser eliminado
            if tokens_actual.issubset(tokens_existente):
                # print(f"  🗑️  '{nombre_actual}' eliminado: subconjunto de '{nombre_existente}'")
                es_valido = False
                break
            
            # CASO 3: El existente es subconjunto del actual
            # Aquí el actual es más largo. Debemos verificar si el actual es válido.
            # Si el actual es válido, eliminamos el existente (más corto) y agregamos el actual.
            # Si el actual NO es válido, mantenemos el existente.
            # Pero ya validamos arriba que el actual es válido, así que podemos reemplazar.
            if tokens_existente.issubset(tokens_actual):
                # print(f"  🔄  '{nombre_existente}' será reemplazado por '{nombre_actual}' (versión más completa)")
                # Eliminar el existente de las listas
                nombres_validos.pop(idx)
                tokens_ya_usados.pop(idx)
                # El actual se agregará después del bucle
                break
        
        if es_valido:
            nombres_validos.append(item['original'])
            tokens_ya_usados.append(tokens_actual)
    
    return nombres_validos


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
        "matricula": validar_matricula,
        "cbu": validar_cbu
    }
    
    validador = validadores.get(tipo_doc)
    
    # Manejo especial para CBU: buscar la palabra "CBU" y luego buscar números cerca
    if tipo_doc == "cbu":
        for match in regex.finditer(texto):
            pos_cbu = match.start()
            
            # Definir ventana de búsqueda: 200 caracteres antes y después de "CBU"
            ventana_inicio = max(0, pos_cbu - 200)
            ventana_fin = min(len(texto), pos_cbu + 200)
            ventana_texto = texto[ventana_inicio:ventana_fin]
            
            # Buscar secuencias de 22 dígitos (con posibles espacios internos)
            # Patrón: 22 dígitos con espacios opcionales entre ellos
            patron_numeros = r'\b(\d(?:\s?\d){20,21})\b'
            
            for num_match in re.finditer(patron_numeros, ventana_texto):
                numero_capturado = num_match.group(1)
                numero_limpio = re.sub(r'\D', '', numero_capturado)
                
                # Validar que tenga exactamente 22 dígitos
                if not validar_cbu(numero_limpio):
                    continue
                
                # Evitar duplicados
                if numero_limpio in numeros_unicos:
                    continue
                
                numeros_unicos.add(numero_limpio)
                
                # Extraer contexto desde la posición real en el texto original
                pos_real = ventana_inicio + num_match.start()
                contexto = _extraer_contexto(texto, pos_real, pos_real + len(numero_capturado), window=60)
                
                documento = {
                    "numero": numero_limpio,
                    "contexto": contexto
                }
                
                documentos_encontrados.append(documento)
        
        return documentos_encontrados
    
    # Para otros documentos, usar el flujo normal
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
        
        # Extraer contexto usando función centralizada
        contexto = _extraer_contexto(texto, match.start(), match.end(), window=60)
        
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
    
    entidades_validas = {"nombre", "nombres", "dni", "matricula", "cuif", "cuit", "cuil", "cbu"}
    entidades_invalidas = set(e.lower().strip() for e in entidades) - entidades_validas
    
    if entidades_invalidas:
        return False, (
            f"Entidades no válidas: {', '.join(entidades_invalidas)}. "
            f"Entidades válidas: nombre (personas), dni (7-8 dígitos), "
            f"matricula (alfanumérico 1-10 chars), cuif (1-10 dígitos), "
            f"cbu (22 dígitos), "
            f"cuit (11 dígitos, prefijos 20-27/30/33-34), cuil (11 dígitos, prefijos 20/23-24/27)"
        )
    return True, None
