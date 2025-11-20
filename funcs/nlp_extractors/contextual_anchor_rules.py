"""
Sistema de Reglas de Anclaje Contextual (Contextual Anchor Rules) usando spaCy Matcher.

Este módulo implementa un sistema extensible para detectar nombres propios basándose
en patrones contextuales específicos encontrados en documentos judiciales.

Reglas implementadas:
1. ANCLAS_CONTEXTUALES: Detecta nombres cerca de palabras-cue con direccionalidad:
   - DERECHA: "Ciudadano RENE ANTONIO" → busca a la derecha del ancla
   - IZQUIERDA: "RENE ANTONIO DNI" → busca a la izquierda del ancla
2. NOMBRE_DESPUES_DE_CONTRA: Detecta nombres después de "contra"
3. PATRON_C_S: Detecta nombres entre "C/" y "S/" (formato expediente judicial)
4. APELLIDO_NOMBRE_JUDICIAL: Detecta formato "Apellido Nombre" (Title Case)
5. NOMBRE_ANTES_DE_C_BARRA: Detecta nombres antes de "C/" (demandante en formato judicial)
6. NOMBRE_JUDICIAL_CON_COMA: Detecta formato "APELLIDO, NOMBRE" (judicial argentino)
"""

from typing import List, Dict, Any, Tuple, Optional
import spacy
from spacy.matcher import Matcher
from funcs.nlp_extractors.constantes import (
    ANCLAS_CONTEXTUALES_DERECHA,
    ANCLAS_CONTEXTUALES_IZQUIERDA,
    ANCLAS_CONTEXTUALES
)


class ContextualAnchorMatcher:
    """
    Detector de nombres basado en reglas de anclaje contextual usando spaCy Matcher.
    
    Permite registrar patrones que identifican nombres propios en contextos específicos,
    sin depender de NER tradicional.
    """
    
    def __init__(self, nlp):
        """
        Inicializa el matcher con el modelo spaCy.
        
        Args:
            nlp: Pipeline de spaCy cargado
        """
        self.nlp = nlp
        self.matcher = Matcher(nlp.vocab)
    
    def add_default_rules(self):
        """
        Registra todas las reglas de anclaje contextual por defecto.
        
        Reglas implementadas:
        1. No se registra en Matcher (se maneja con lógica custom en _detectar_anclas_contextuales)
        2. NOMBRE_DESPUES_DE_CONTRA: "contra" + 2-6 tokens mayúsculas
        3. PATRON_C_S: Nombres entre "C/" y "S/" (expedientes judiciales)
        4. APELLIDO_NOMBRE_JUDICIAL: Formato Title Case (2+ tokens)
        5. NOMBRE_ANTES_DE_C_BARRA: Nombres antes de "C/" (demandante en formato judicial)
        6. NOMBRE_JUDICIAL_CON_COMA: Detecta formato "APELLIDO, NOMBRE" (judicial argentino)
        """
        # ========== REGLA 2: "contra" + nombres en MAYÚSCULAS ==========
        # Requiere tokens de al menos 2 caracteres para evitar letras sueltas
        patron_contra = [
            {"LOWER": "contra"},
            {"IS_ALPHA": True, "IS_UPPER": True, "LENGTH": {">=": 2}},  # Token 1 (obligatorio, min 2 chars)
            {"IS_ALPHA": True, "IS_UPPER": True, "LENGTH": {">=": 2}},  # Token 2 (obligatorio, min 2 chars)
            {"IS_ALPHA": True, "IS_UPPER": True, "LENGTH": {">=": 2}, "OP": "?"},  # Token 3 (opcional)
            {"IS_ALPHA": True, "IS_UPPER": True, "LENGTH": {">=": 2}, "OP": "?"},  # Token 4 (opcional)
            {"IS_ALPHA": True, "IS_UPPER": True, "LENGTH": {">=": 2}, "OP": "?"},  # Token 5 (opcional)
            {"IS_ALPHA": True, "IS_UPPER": True, "LENGTH": {">=": 2}, "OP": "?"},  # Token 6 (opcional)
        ]
        self.matcher.add("NOMBRE_DESPUES_DE_CONTRA", [patron_contra], greedy="LONGEST")
        
        # ========== REGLA 4: Apellido + Nombre (Title Case) ==========
        # Formato: "Codazzi Luis", "Daniel Ernesto D'Avis", "Fernando Augusto Niz"
        # Mínimo 2 tokens Title Case, máximo 6
        # Requiere tokens de al menos 2 caracteres para evitar "S E N T E N C I A"
        patron_apellido_nombre = [
            {"IS_ALPHA": True, "IS_TITLE": True, "LENGTH": {">=": 2}},  # Token 1: obligatorio (min 2 chars)
            {"IS_ALPHA": True, "IS_TITLE": True, "LENGTH": {">=": 2}},  # Token 2: obligatorio (min 2 chars)
            {"IS_ALPHA": True, "IS_TITLE": True, "LENGTH": {">=": 2}, "OP": "?"},  # Token 3: opcional
            {"IS_ALPHA": True, "IS_TITLE": True, "LENGTH": {">=": 2}, "OP": "?"},  # Token 4: opcional
            {"IS_ALPHA": True, "IS_TITLE": True, "LENGTH": {">=": 2}, "OP": "?"},  # Token 5: opcional
            {"IS_ALPHA": True, "IS_TITLE": True, "LENGTH": {">=": 2}, "OP": "?"},  # Token 6: opcional
        ]
        self.matcher.add("APELLIDO_NOMBRE_JUDICIAL", [patron_apellido_nombre], greedy="LONGEST")
    
    def find_matches(self, doc) -> List[Dict[str, Any]]:
        """
        Encuentra todas las coincidencias de reglas de anclaje en el documento.
        
        Ejecuta las reglas en orden:
        1. ANCLAS_CONTEXTUALES (lógica custom)
        2. Matcher de spaCy (reglas 2, 4)
        3. PATRON_C_S (lógica custom)
        4. NOMBRE_ANTES_DE_C_BARRA (lógica custom)
        
        Args:
            doc: Documento procesado por spaCy
            
        Returns:
            Lista de diccionarios con información de cada coincidencia:
            [
                {
                    "rule": "NOMBRE_DESPUES_DE_CONTRA",
                    "anchor": "contra",
                    "matched_text": "contra PÉREZ CARLOS",
                    "name_tokens": ["PÉREZ", "CARLOS"],
                    "span_start": 15,
                    "span_end": 35,
                    "context": "...el juicio contra PÉREZ CARLOS en el..."
                }
            ]
        """
        resultados = []
        
        # ========== REGLA 1: ANCLAS_CONTEXTUALES ==========
        anclas_matches = self._detectar_anclas_contextuales(doc)
        resultados.extend(anclas_matches)
        
        # ========== REGLA 3: PATRON_C_S ==========
        patron_cs_matches = self._detectar_patron_c_s(doc)
        resultados.extend(patron_cs_matches)
        
        # ========== REGLA 5: NOMBRE_ANTES_DE_C_BARRA ==========
        nombre_antes_c_matches = self._detectar_nombre_antes_de_c_barra(doc)
        resultados.extend(nombre_antes_c_matches)
        
        # ========== REGLA 6: NOMBRE_JUDICIAL_CON_COMA ==========
        nombre_coma_matches = self._detectar_nombre_judicial_con_coma(doc)
        resultados.extend(nombre_coma_matches)
        
        # ========== REGLAS 2 y 4: Matcher de spaCy ==========
        matches = self.matcher(doc)
        
        for match_id, start, end in matches:
            rule_name = self.nlp.vocab.strings[match_id]
            span = doc[start:end]
            matched_text = span.text
            
            # Determinar ancla y tokens según la regla
            if rule_name == "NOMBRE_DESPUES_DE_CONTRA":
                anchor = "contra"
                name_tokens = [token.text for token in span[1:]]  # Excluir "contra"
            elif rule_name == "APELLIDO_NOMBRE_JUDICIAL":
                anchor = "title_case"
                name_tokens = [token.text for token in span]
            else:
                anchor = "unknown"
                name_tokens = [token.text for token in span]
            
            # Extraer contexto (60 caracteres antes y después)
            span_start_char = span.start_char
            span_end_char = span.end_char
            
            ctx_start = max(0, span_start_char - 60)
            ctx_end = min(len(doc.text), span_end_char + 60)
            context = doc.text[ctx_start:ctx_end].strip()
            
            resultado = {
                "rule": rule_name,
                "anchor": anchor,
                "matched_text": matched_text,
                "name_tokens": name_tokens,
                "span_start": span_start_char,
                "span_end": span_end_char,
                "context": context
            }
            
            resultados.append(resultado)
        
        return resultados
    
    def extract_names(self, doc) -> List[str]:
        """
        Extrae únicamente los nombres detectados por las reglas de anclaje.
        
        Args:
            doc: Documento procesado por spaCy
            
        Returns:
            Lista de nombres detectados (sin el ancla):
            ["PÉREZ CARLOS", "GARCÍA MARÍA"]
        """
        matches = self.find_matches(doc)
        
        nombres = []
        for match in matches:
            # Unir los tokens del nombre en un string
            nombre_completo = " ".join(match["name_tokens"])
            if nombre_completo:
                nombres.append(nombre_completo)
        
        return nombres
    
    def _detectar_anclas_contextuales(self, doc) -> List[Dict[str, Any]]:
        """
        REGLA 1: Detecta nombres cerca de anclas contextuales.
        
        - ANCLAS_DERECHA: busca nombres a la DERECHA del ancla (ej: "Ciudadano RENE ANTONIO")
        - ANCLAS_IZQUIERDA: busca nombres a la IZQUIERDA del ancla (ej: "RENE ANTONIO DNI")
        
        Args:
            doc: Documento procesado por spaCy
            
        Returns:
            Lista de matches con la estructura estándar
        """
        resultados = []
        texto = doc.text.lower()
        
        # ========== PROCESAR ANCLAS DERECHA (nombre después del ancla) ==========
        for ancla in ANCLAS_CONTEXTUALES_DERECHA:
            pos = 0
            while True:
                pos = texto.find(ancla, pos)
                if pos == -1:
                    break
                
                # Ventana: desde el FINAL del ancla hasta +70 caracteres
                ancla_end = pos + len(ancla)
                ventana_start = ancla_end
                ventana_end = min(len(doc.text), ancla_end + 70)
                
                # Encontrar tokens a la DERECHA del ancla
                tokens_en_ventana = []
                for token in doc:
                    if ventana_start <= token.idx < ventana_end:
                        tokens_en_ventana.append(token)
                
                # Buscar secuencias de 2-6 tokens consecutivos válidos
                nombre_detectado = self._buscar_nombre_en_tokens(
                    tokens_en_ventana, doc, ancla, "ANCLAS_CONTEXTUALES_DERECHA"
                )
                if nombre_detectado:
                    resultados.append(nombre_detectado)
                
                pos += len(ancla)
        
        # ========== PROCESAR ANCLAS IZQUIERDA (nombre antes del ancla) ==========
        for ancla in ANCLAS_CONTEXTUALES_IZQUIERDA:
            pos = 0
            while True:
                pos = texto.find(ancla, pos)
                if pos == -1:
                    break
                
                # Ventana: desde -70 caracteres hasta el INICIO del ancla
                ventana_start = max(0, pos - 70)
                ventana_end = pos
                
                # Encontrar tokens a la IZQUIERDA del ancla
                tokens_en_ventana = []
                for token in doc:
                    if ventana_start <= token.idx < ventana_end:
                        tokens_en_ventana.append(token)
                
                # Buscar secuencias de 2-6 tokens consecutivos válidos
                # Para izquierda, queremos el ÚLTIMO grupo de tokens válidos antes del ancla
                nombre_detectado = self._buscar_nombre_en_tokens_izquierda(
                    tokens_en_ventana, doc, ancla, "ANCLAS_CONTEXTUALES_IZQUIERDA"
                )
                if nombre_detectado:
                    resultados.append(nombre_detectado)
                
                pos += len(ancla)
        
        return resultados
    
    def _buscar_nombre_en_tokens(
        self, 
        tokens_en_ventana: List, 
        doc, 
        ancla: str, 
        rule_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Busca el PRIMER nombre válido (2-6 tokens) a la DERECHA.
        Retorna el primer match encontrado o None.
        
        VALIDACIÓN: Cada token debe tener al menos 2 caracteres para evitar
        detectar letras sueltas como "S E N T E N C I A".
        """
        for i in range(len(tokens_en_ventana)):
            token_inicial = tokens_en_ventana[i]
            
            # Verificar condiciones del token inicial (min 2 caracteres)
            if not token_inicial.is_alpha or not token_inicial.text[0].isupper() or len(token_inicial.text) < 2:
                continue
            
            # Acumular tokens consecutivos válidos (cada uno con min 2 caracteres)
            tokens_candidatos = [token_inicial]
            for j in range(i + 1, min(i + 6, len(tokens_en_ventana))):
                token_siguiente = tokens_en_ventana[j]
                if token_siguiente.is_alpha and token_siguiente.text[0].isupper() and len(token_siguiente.text) >= 2:
                    tokens_candidatos.append(token_siguiente)
                else:
                    break
            
            # Validar cantidad de tokens
            if 2 <= len(tokens_candidatos) <= 6:
                span_start = tokens_candidatos[0].idx
                span_end = tokens_candidatos[-1].idx + len(tokens_candidatos[-1].text)
                matched_text = doc.text[span_start:span_end]
                name_tokens = [t.text for t in tokens_candidatos]
                
                # Extraer contexto
                ctx_start = max(0, span_start - 60)
                ctx_end = min(len(doc.text), span_end + 60)
                context = doc.text[ctx_start:ctx_end].strip()
                
                return {
                    "rule": rule_name,
                    "anchor": ancla,
                    "matched_text": matched_text,
                    "name_tokens": name_tokens,
                    "span_start": span_start,
                    "span_end": span_end,
                    "context": context
                }
        
        return None
    
    def _buscar_nombre_en_tokens_izquierda(
        self, 
        tokens_en_ventana: List, 
        doc, 
        ancla: str, 
        rule_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Busca el ÚLTIMO nombre válido (2-6 tokens) a la IZQUIERDA.
        Retorna el último match encontrado (más cercano al ancla) o None.
        
        VALIDACIÓN: Cada token debe tener al menos 2 caracteres para evitar
        detectar letras sueltas como "S E N T E N C I A".
        """
        mejor_match = None
        
        # Iterar desde el final hacia el inicio para encontrar el más cercano al ancla
        for i in range(len(tokens_en_ventana) - 1, -1, -1):
            token_inicial = tokens_en_ventana[i]
            
            # Verificar condiciones del token inicial (min 2 caracteres)
            if not token_inicial.is_alpha or not token_inicial.text[0].isupper() or len(token_inicial.text) < 2:
                continue
            
            # Acumular tokens consecutivos válidos hacia la izquierda (cada uno con min 2 caracteres)
            tokens_candidatos = [token_inicial]
            for j in range(i - 1, max(-1, i - 6), -1):
                if j < 0:
                    break
                token_anterior = tokens_en_ventana[j]
                if token_anterior.is_alpha and token_anterior.text[0].isupper() and len(token_anterior.text) >= 2:
                    tokens_candidatos.insert(0, token_anterior)
                else:
                    break
            
            # Validar cantidad de tokens
            if 2 <= len(tokens_candidatos) <= 6:
                span_start = tokens_candidatos[0].idx
                span_end = tokens_candidatos[-1].idx + len(tokens_candidatos[-1].text)
                matched_text = doc.text[span_start:span_end]
                name_tokens = [t.text for t in tokens_candidatos]
                
                # Extraer contexto
                ctx_start = max(0, span_start - 60)
                ctx_end = min(len(doc.text), span_end + 60)
                context = doc.text[ctx_start:ctx_end].strip()
                
                mejor_match = {
                    "rule": rule_name,
                    "anchor": ancla,
                    "matched_text": matched_text,
                    "name_tokens": name_tokens,
                    "span_start": span_start,
                    "span_end": span_end,
                    "context": context
                }
                
                # Retornar inmediatamente el más cercano al ancla
                return mejor_match
        
        return mejor_match
    
    def _detectar_patron_c_s(self, doc) -> List[Dict[str, Any]]:
        """
        REGLA 3: Detecta nombres entre "C/" y "S/" (formato expediente judicial).
        
        Ejemplo: "GARCIA VANINA MARISOL C/ QUER MULLER RENE ANTONIO S/ LEY 5019"
        Extrae: "QUER MULLER RENE ANTONIO"
        
        Args:
            doc: Documento procesado por spaCy
            
        Returns:
            Lista de matches con la estructura estándar
        """
        resultados = []
        
        # Buscar tokens "C/" o "C."
        indices_c = []
        indices_s = []
        
        for i, token in enumerate(doc):
            if token.text in ("C/", "C.", "c/", "c."):
                indices_c.append(i)
            elif token.text in ("S/", "S.", "s/", "s."):
                indices_s.append(i)
        
        # Para cada "C/", buscar el "S/" más cercano a la derecha
        for idx_c in indices_c:
            # Buscar "S/" a la derecha (máximo 30 tokens adelante)
            idx_s = None
            for idx in indices_s:
                if idx_c < idx <= idx_c + 30:
                    idx_s = idx
                    break
            
            if idx_s is None:
                continue
            
            # Extraer tokens entre C/ y S/ (min 2 caracteres cada token)
            tokens_entre = []
            for i in range(idx_c + 1, idx_s):
                token = doc[i]
                if token.is_alpha and token.text[0].isupper() and len(token.text) >= 2:
                    tokens_entre.append(token)
                elif tokens_entre:  # Si ya empezamos a acumular, detener al encontrar no-alpha
                    break
            
            # Validar que haya entre 2 y 6 tokens
            if 2 <= len(tokens_entre) <= 6:
                span_start = tokens_entre[0].idx
                span_end = tokens_entre[-1].idx + len(tokens_entre[-1].text)
                matched_text = doc.text[span_start:span_end]
                name_tokens = [t.text for t in tokens_entre]
                
                # Extraer contexto
                ctx_start = max(0, span_start - 60)
                ctx_end = min(len(doc.text), span_end + 60)
                context = doc.text[ctx_start:ctx_end].strip()
                
                resultado = {
                    "rule": "PATRON_C_S",
                    "anchor": "C/...S/",
                    "matched_text": matched_text,
                    "name_tokens": name_tokens,
                    "span_start": span_start,
                    "span_end": span_end,
                    "context": context
                }
                
                resultados.append(resultado)
        
        return resultados
    
    def _detectar_nombre_antes_de_c_barra(self, doc) -> List[Dict[str, Any]]:
        """
        REGLA 5: Detecta nombres ANTES de "C/" (demandante en formato judicial).
        
        Ejemplo: "DORNELL VICTOR C/ PODER EJECUTIVO"
        Extrae: "DORNELL VICTOR"
        
        Args:
            doc: Documento procesado por spaCy
            
        Returns:
            Lista de matches con la estructura estándar
        """
        resultados = []
        
        # Buscar tokens "C/" o "C."
        indices_c = []
        for i, token in enumerate(doc):
            if token.text in ("C/", "C.", "c/", "c."):
                indices_c.append(i)
        
        # Para cada "C/", buscar nombre a la IZQUIERDA (70 caracteres antes)
        for idx_c in indices_c:
            token_c = doc[idx_c]
            pos_c = token_c.idx
            
            # Ventana: desde -70 caracteres hasta el inicio de "C/"
            ventana_start = max(0, pos_c - 70)
            ventana_end = pos_c
            
            # Encontrar tokens a la IZQUIERDA de "C/"
            tokens_en_ventana = []
            for token in doc:
                if ventana_start <= token.idx < ventana_end:
                    tokens_en_ventana.append(token)
            
            # Buscar el ÚLTIMO grupo de 2-6 tokens en MAYÚSCULAS antes de "C/"
            # (el más cercano a "C/" es el demandante)
            mejor_match = None
            
            for i in range(len(tokens_en_ventana) - 1, -1, -1):
                token_inicial = tokens_en_ventana[i]
                
                # Verificar que sea alfabético, empiece en mayúscula y tenga min 2 caracteres
                if not token_inicial.is_alpha or not token_inicial.text[0].isupper() or len(token_inicial.text) < 2:
                    continue
                
                # Acumular tokens consecutivos válidos hacia la izquierda (min 2 caracteres cada uno)
                tokens_candidatos = [token_inicial]
                for j in range(i - 1, max(-1, i - 6), -1):
                    if j < 0:
                        break
                    token_anterior = tokens_en_ventana[j]
                    if token_anterior.is_alpha and token_anterior.text[0].isupper() and len(token_anterior.text) >= 2:
                        tokens_candidatos.insert(0, token_anterior)
                    else:
                        break
                
                # Validar cantidad de tokens (2-6)
                if 2 <= len(tokens_candidatos) <= 6:
                    span_start = tokens_candidatos[0].idx
                    span_end = tokens_candidatos[-1].idx + len(tokens_candidatos[-1].text)
                    matched_text = doc.text[span_start:span_end]
                    name_tokens = [t.text for t in tokens_candidatos]
                    
                    # Extraer contexto
                    ctx_start = max(0, span_start - 60)
                    ctx_end = min(len(doc.text), span_end + 60)
                    context = doc.text[ctx_start:ctx_end].strip()
                    
                    mejor_match = {
                        "rule": "NOMBRE_ANTES_DE_C_BARRA",
                        "anchor": "C/",
                        "matched_text": matched_text,
                        "name_tokens": name_tokens,
                        "span_start": span_start,
                        "span_end": span_end,
                        "context": context
                    }
                    
                    # Retornar el más cercano al "C/"
                    break
            
            if mejor_match:
                resultados.append(mejor_match)
        
        return resultados
    
    def _detectar_nombre_judicial_con_coma(self, doc) -> List[Dict[str, Any]]:
        """
        REGLA 6: Detecta nombres en formato judicial con coma: "APELLIDO, NOMBRE".
        
        Ejemplo: "CARBALLO, MARTA" → extrae "CARBALLO, MARTA" (preservando la coma original)
        Formato común en expedientes judiciales argentinos.
        
        Args:
            doc: Documento procesado por spaCy
            
        Returns:
            Lista de matches con la estructura estándar
        """
        import re
        resultados = []
        
        # Patrón: 1-3 tokens MAYÚSCULAS + COMA + 1-3 tokens MAYÚSCULAS
        # "CARBALLO, MARTA" o "GARCÍA LÓPEZ, JUAN CARLOS"
        patron = re.compile(
            r'\b([A-ZÁÉÍÓÚÑ]{2,}(?:\s+[A-ZÁÉÍÓÚÑ]{2,}){0,2}),\s+([A-ZÁÉÍÓÚÑ]{2,}(?:\s+[A-ZÁÉÍÓÚÑ]{2,}){0,2})\b'
        )
        
        for match in patron.finditer(doc.text):
            apellido = match.group(1)  # Parte antes de la coma
            nombre = match.group(2)    # Parte después de la coma
            
            # Verificar que cada parte tenga al menos 2 caracteres
            if len(apellido) < 2 or len(nombre) < 2:
                continue
            
            # Construir nombre completo CON coma (preservando formato original del PDF)
            nombre_completo_con_coma = f"{apellido}, {nombre}"
            
            # Para validación, contar tokens sin la coma
            tokens_sin_coma = apellido.split() + nombre.split()
            
            # Validar cantidad total de tokens (2-6)
            if not (2 <= len(tokens_sin_coma) <= 6):
                continue
            
            span_start = match.start()
            span_end = match.end()
            matched_text = match.group(0)  # Con coma (original)
            
            # Extraer contexto
            ctx_start = max(0, span_start - 60)
            ctx_end = min(len(doc.text), span_end + 60)
            context = doc.text[ctx_start:ctx_end].strip()
            
            # CAMBIO CLAVE: Retornar el nombre CON la coma original
            # name_tokens incluye el nombre completo con coma preservada
            resultado = {
                "rule": "NOMBRE_JUDICIAL_CON_COMA",
                "anchor": "coma_judicial",
                "matched_text": matched_text,
                "name_tokens": tokens_sin_coma,  # Tokens sin coma para procesamiento interno
                "nombre_original": nombre_completo_con_coma,  # Con coma preservada para output
                "span_start": span_start,
                "span_end": span_end,
                "context": context
            }
            
            resultados.append(resultado)
        
        return resultados
