"""
Sistema de Reglas de Anclaje Contextual para detectar nombres en documentos judiciales.
Implementa 6 reglas contextuales usando spaCy Matcher.
"""

from typing import List, Dict, Any, Tuple, Optional
import re
import spacy
from spacy.matcher import Matcher
from funcs.nlp_extractors.constantes import (
    ANCLAS_CONTEXTUALES_DERECHA,
    ANCLAS_CONTEXTUALES_IZQUIERDA,
    ANCLAS_CONTEXTUALES
)

# Compilar regex una sola vez (módulo-level) para mejor rendimiento
_PATRON_NOMBRE_COMA = re.compile(
    r'\b([A-ZÁÉÍÓÚÑ]{2,}(?:\s+[A-ZÁÉÍÓÚÑ]{2,}){0,2}),\s+([A-ZÁÉÍÓÚÑ]{2,}(?:\s+[A-ZÁÉÍÓÚÑ]{2,}){0,2})\b'
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
        # Cache para tokens indexados por posición (evita recálculos)
        self._token_cache = {}
    
    def _extraer_contexto(self, doc_text: str, start: int, end: int, window: int = 60) -> str:
        """
        Extrae contexto alrededor de un span (optimizado, reutilizable).
        
        Args:
            doc_text: Texto completo del documento
            start: Posición inicial del span
            end: Posición final del span
            window: Ventana de contexto (caracteres antes/después)
        
        Returns:
            Contexto extraído
        """
        ctx_start = max(0, start - window)
        ctx_end = min(len(doc_text), end + window)
        return doc_text[ctx_start:ctx_end].strip()
    
    def add_default_rules(self):
        """Registra las 6 reglas contextuales por defecto."""
        # REGLA 2: "contra" + nombres en MAYÚSCULAS (2-6 tokens, mínimo 2 caracteres)
        patron_contra = [
            {"LOWER": "contra"},
            {"IS_ALPHA": True, "IS_UPPER": True, "LENGTH": {">=": 2}},
            {"IS_ALPHA": True, "IS_UPPER": True, "LENGTH": {">=": 2}},
            {"IS_ALPHA": True, "IS_UPPER": True, "LENGTH": {">=": 2}, "OP": "?"},
            {"IS_ALPHA": True, "IS_UPPER": True, "LENGTH": {">=": 2}, "OP": "?"},
            {"IS_ALPHA": True, "IS_UPPER": True, "LENGTH": {">=": 2}, "OP": "?"},
            {"IS_ALPHA": True, "IS_UPPER": True, "LENGTH": {">=": 2}, "OP": "?"},
        ]
        self.matcher.add("NOMBRE_DESPUES_DE_CONTRA", [patron_contra], greedy="LONGEST")
        
        # REGLA 4: Apellido + Nombre (Title Case, 2-6 tokens, mínimo 2 caracteres)
        patron_apellido_nombre = [
            {"IS_ALPHA": True, "IS_TITLE": True, "LENGTH": {">=": 2}},
            {"IS_ALPHA": True, "IS_TITLE": True, "LENGTH": {">=": 2}},
            {"IS_ALPHA": True, "IS_TITLE": True, "LENGTH": {">=": 2}, "OP": "?"},
            {"IS_ALPHA": True, "IS_TITLE": True, "LENGTH": {">=": 2}, "OP": "?"},
            {"IS_ALPHA": True, "IS_TITLE": True, "LENGTH": {">=": 2}, "OP": "?"},
            {"IS_ALPHA": True, "IS_TITLE": True, "LENGTH": {">=": 2}, "OP": "?"},
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
        REGLA 1: Detecta nombres cerca de anclas contextuales (OPTIMIZADO).
        
        - ANCLAS_DERECHA: busca nombres a la DERECHA del ancla (ej: "Ciudadano RENE ANTONIO")
        - ANCLAS_IZQUIERDA: busca nombres a la IZQUIERDA del ancla (ej: "RENE ANTONIO DNI")
        
        OPTIMIZACIÓN: Itera sobre tokens una sola vez y usa índice pre-construido.
        
        Args:
            doc: Documento procesado por spaCy
            
        Returns:
            Lista de matches con la estructura estándar
        """
        resultados = []
        texto_lower = doc.text.lower()
        doc_text = doc.text
        
        # OPTIMIZACIÓN: Construir índice de tokens por posición de caracteres (una sola vez)
        # Esto evita iterar sobre todos los tokens en cada búsqueda de ventana
        if id(doc) not in self._token_cache:
            token_por_posicion = []
            for token in doc:
                token_por_posicion.append((token.idx, token))
            self._token_cache[id(doc)] = token_por_posicion
        else:
            token_por_posicion = self._token_cache[id(doc)]
        
        # ========== PROCESAR ANCLAS DERECHA (nombre después del ancla) ==========
        # OPTIMIZACIÓN: Crear regex pattern para buscar todas las anclas de una vez
        if ANCLAS_CONTEXTUALES_DERECHA:
            # Escapar caracteres especiales y unir con |
            anclas_escaped = [re.escape(a) for a in ANCLAS_CONTEXTUALES_DERECHA]
            pattern_derecha = re.compile('|'.join(anclas_escaped), re.IGNORECASE)
            
            for match in pattern_derecha.finditer(texto_lower):
                ancla = match.group()
                pos = match.start()
                
                # Ventana: desde el FINAL del ancla hasta +70 caracteres
                ancla_end = pos + len(ancla)
                ventana_start = ancla_end
                ventana_end = min(len(doc_text), ancla_end + 70)
                
                # OPTIMIZACIÓN: Buscar tokens en ventana usando búsqueda binaria/filtrado eficiente
                tokens_en_ventana = [tok for pos_idx, tok in token_por_posicion 
                                     if ventana_start <= pos_idx < ventana_end]
                
                # Buscar secuencias de 2-6 tokens consecutivos válidos
                nombre_detectado = self._buscar_nombre_en_tokens(
                    tokens_en_ventana, doc_text, ancla, "ANCLAS_CONTEXTUALES_DERECHA"
                )
                if nombre_detectado:
                    resultados.append(nombre_detectado)
        
        # ========== PROCESAR ANCLAS IZQUIERDA (nombre antes del ancla) ==========
        if ANCLAS_CONTEXTUALES_IZQUIERDA:
            anclas_escaped = [re.escape(a) for a in ANCLAS_CONTEXTUALES_IZQUIERDA]
            pattern_izquierda = re.compile('|'.join(anclas_escaped), re.IGNORECASE)
            
            for match in pattern_izquierda.finditer(texto_lower):
                ancla = match.group()
                pos = match.start()
                
                # Ventana: desde -70 caracteres hasta el INICIO del ancla
                ventana_start = max(0, pos - 70)
                ventana_end = pos
                
                # Encontrar tokens a la IZQUIERDA del ancla
                tokens_en_ventana = [tok for pos_idx, tok in token_por_posicion 
                                     if ventana_start <= pos_idx < ventana_end]
                
                # Buscar secuencias de 2-6 tokens consecutivos válidos
                nombre_detectado = self._buscar_nombre_en_tokens_izquierda(
                    tokens_en_ventana, doc_text, ancla, "ANCLAS_CONTEXTUALES_IZQUIERDA"
                )
                if nombre_detectado:
                    resultados.append(nombre_detectado)
        
        return resultados
    
    def _buscar_nombre_en_tokens(
        self, 
        tokens_en_ventana: List, 
        doc_text: str, 
        ancla: str, 
        rule_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Busca el PRIMER nombre válido (2-6 tokens) a la DERECHA (OPTIMIZADO).
        Retorna el primer match encontrado o None.
        
        VALIDACIÓN: Cada token debe tener al menos 2 caracteres para evitar
        detectar letras sueltas como "S E N T E N C I A".
        """
        ventana_len = len(tokens_en_ventana)
        
        for i in range(ventana_len):
            token_inicial = tokens_en_ventana[i]
            
            # Verificar condiciones del token inicial (min 2 caracteres)
            text_inicial = token_inicial.text
            if not token_inicial.is_alpha or not text_inicial[0].isupper() or len(text_inicial) < 2:
                continue
            
            # Acumular tokens consecutivos válidos (cada uno con min 2 caracteres)
            tokens_candidatos = [token_inicial]
            max_j = min(i + 6, ventana_len)
            
            for j in range(i + 1, max_j):
                token_siguiente = tokens_en_ventana[j]
                text_siguiente = token_siguiente.text
                if token_siguiente.is_alpha and text_siguiente[0].isupper() and len(text_siguiente) >= 2:
                    tokens_candidatos.append(token_siguiente)
                else:
                    break
            
            # Validar cantidad de tokens
            if 2 <= len(tokens_candidatos) <= 6:
                span_start = tokens_candidatos[0].idx
                last_token = tokens_candidatos[-1]
                span_end = last_token.idx + len(last_token.text)
                
                return {
                    "rule": rule_name,
                    "anchor": ancla,
                    "matched_text": doc_text[span_start:span_end],
                    "name_tokens": [t.text for t in tokens_candidatos],
                    "span_start": span_start,
                    "span_end": span_end,
                    "context": self._extraer_contexto(doc_text, span_start, span_end)
                }
        
        return None
    
    def _buscar_nombre_en_tokens_izquierda(
        self, 
        tokens_en_ventana: List, 
        doc_text: str, 
        ancla: str, 
        rule_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Busca el ÚLTIMO nombre válido (2-6 tokens) a la IZQUIERDA (OPTIMIZADO).
        Retorna el último match encontrado (más cercano al ancla) o None.
        
        VALIDACIÓN: Cada token debe tener al menos 2 caracteres para evitar
        detectar letras sueltas como "S E N T E N C I A".
        """
        # Iterar desde el final hacia el inicio para encontrar el más cercano al ancla
        for i in range(len(tokens_en_ventana) - 1, -1, -1):
            token_inicial = tokens_en_ventana[i]
            
            # Verificar condiciones del token inicial (min 2 caracteres)
            text_inicial = token_inicial.text
            if not token_inicial.is_alpha or not text_inicial[0].isupper() or len(text_inicial) < 2:
                continue
            
            # Acumular tokens consecutivos válidos hacia la izquierda (cada uno con min 2 caracteres)
            tokens_candidatos = [token_inicial]
            min_j = max(-1, i - 6)
            
            for j in range(i - 1, min_j, -1):
                if j < 0:
                    break
                token_anterior = tokens_en_ventana[j]
                text_anterior = token_anterior.text
                if token_anterior.is_alpha and text_anterior[0].isupper() and len(text_anterior) >= 2:
                    tokens_candidatos.insert(0, token_anterior)
                else:
                    break
            
            # Validar cantidad de tokens
            if 2 <= len(tokens_candidatos) <= 6:
                span_start = tokens_candidatos[0].idx
                last_token = tokens_candidatos[-1]
                span_end = last_token.idx + len(last_token.text)
                
                # Retornar inmediatamente el más cercano al ancla (primera coincidencia válida)
                return {
                    "rule": rule_name,
                    "anchor": ancla,
                    "matched_text": doc_text[span_start:span_end],
                    "name_tokens": [t.text for t in tokens_candidatos],
                    "span_start": span_start,
                    "span_end": span_end,
                    "context": self._extraer_contexto(doc_text, span_start, span_end)
                }
        
        return None
    
    def _detectar_patron_c_s(self, doc) -> List[Dict[str, Any]]:
        """
        REGLA 3: Detecta nombres entre "C/" y "S/" (formato expediente judicial) (OPTIMIZADO).
        
        Ejemplo: "GARCIA VANINA MARISOL C/ QUER MULLER RENE ANTONIO S/ LEY 5019"
        Extrae: "QUER MULLER RENE ANTONIO"
        
        Args:
            doc: Documento procesado por spaCy
            
        Returns:
            Lista de matches con la estructura estándar
        """
        resultados = []
        doc_text = doc.text
        
        # OPTIMIZACIÓN: Set para búsqueda O(1) y listas para orden
        marcadores_c = {"C/", "C.", "c/", "c."}
        marcadores_s = {"S/", "S.", "s/", "s."}
        
        indices_c = []
        indices_s = []
        
        # Una sola iteración sobre tokens
        for i, token in enumerate(doc):
            token_text = token.text
            if token_text in marcadores_c:
                indices_c.append(i)
            elif token_text in marcadores_s:
                indices_s.append(i)
        
        # Para cada "C/", buscar el "S/" más cercano a la derecha
        for idx_c in indices_c:
            # OPTIMIZACIÓN: Búsqueda temprana + límite
            idx_s = None
            limite = idx_c + 30
            
            for idx in indices_s:
                if idx_c < idx <= limite:
                    idx_s = idx
                    break
                elif idx > limite:
                    break  # Ya no hay matches posibles
            
            if idx_s is None:
                continue
            
            # Extraer tokens entre C/ y S/ (min 2 caracteres cada token)
            tokens_entre = []
            for i in range(idx_c + 1, idx_s):
                token = doc[i]
                token_text = token.text
                
                if token.is_alpha and token_text[0].isupper() and len(token_text) >= 2:
                    tokens_entre.append(token)
                elif tokens_entre:  # Si ya empezamos a acumular, detener al encontrar no-alpha
                    break
            
            # Validar que haya entre 2 y 6 tokens
            if 2 <= len(tokens_entre) <= 6:
                span_start = tokens_entre[0].idx
                last_token = tokens_entre[-1]
                span_end = last_token.idx + len(last_token.text)
                
                resultados.append({
                    "rule": "PATRON_C_S",
                    "anchor": "C/...S/",
                    "matched_text": doc_text[span_start:span_end],
                    "name_tokens": [t.text for t in tokens_entre],
                    "span_start": span_start,
                    "span_end": span_end,
                    "context": self._extraer_contexto(doc_text, span_start, span_end)
                })
        
        return resultados
    
    def _detectar_nombre_antes_de_c_barra(self, doc) -> List[Dict[str, Any]]:
        """
        REGLA 5: Detecta nombres ANTES de "C/" (demandante en formato judicial) (OPTIMIZADO).
        
        Ejemplo: "DORNELL VICTOR C/ PODER EJECUTIVO"
        Extrae: "DORNELL VICTOR"
        
        Args:
            doc: Documento procesado por spaCy
            
        Returns:
            Lista de matches con la estructura estándar
        """
        resultados = []
        doc_text = doc.text
        marcadores_c = {"C/", "C.", "c/", "c."}
        
        # Reutilizar índice de tokens si existe
        if id(doc) not in self._token_cache:
            token_por_posicion = [(token.idx, token) for token in doc]
            self._token_cache[id(doc)] = token_por_posicion
        else:
            token_por_posicion = self._token_cache[id(doc)]
        
        # Buscar tokens "C/" o "C."
        indices_c = [i for i, token in enumerate(doc) if token.text in marcadores_c]
        
        # Para cada "C/", buscar nombre a la IZQUIERDA (70 caracteres antes)
        for idx_c in indices_c:
            token_c = doc[idx_c]
            pos_c = token_c.idx
            
            # Ventana: desde -70 caracteres hasta el inicio de "C/"
            ventana_start = max(0, pos_c - 70)
            ventana_end = pos_c
            
            # OPTIMIZACIÓN: Filtrado directo con list comprehension
            tokens_en_ventana = [tok for pos_idx, tok in token_por_posicion 
                                 if ventana_start <= pos_idx < ventana_end]
            
            if not tokens_en_ventana:
                continue
            
            # Buscar el ÚLTIMO grupo de 2-6 tokens en MAYÚSCULAS antes de "C/"
            for i in range(len(tokens_en_ventana) - 1, -1, -1):
                token_inicial = tokens_en_ventana[i]
                text_inicial = token_inicial.text
                
                # Verificar que sea alfabético, empiece en mayúscula y tenga min 2 caracteres
                if not token_inicial.is_alpha or not text_inicial[0].isupper() or len(text_inicial) < 2:
                    continue
                
                # Acumular tokens consecutivos válidos hacia la izquierda
                tokens_candidatos = [token_inicial]
                min_j = max(-1, i - 6)
                
                for j in range(i - 1, min_j, -1):
                    if j < 0:
                        break
                    token_anterior = tokens_en_ventana[j]
                    text_anterior = token_anterior.text
                    if token_anterior.is_alpha and text_anterior[0].isupper() and len(text_anterior) >= 2:
                        tokens_candidatos.insert(0, token_anterior)
                    else:
                        break
                
                # Validar cantidad de tokens (2-6)
                if 2 <= len(tokens_candidatos) <= 6:
                    span_start = tokens_candidatos[0].idx
                    last_token = tokens_candidatos[-1]
                    span_end = last_token.idx + len(last_token.text)
                    
                    resultados.append({
                        "rule": "NOMBRE_ANTES_DE_C_BARRA",
                        "anchor": "C/",
                        "matched_text": doc_text[span_start:span_end],
                        "name_tokens": [t.text for t in tokens_candidatos],
                        "span_start": span_start,
                        "span_end": span_end,
                        "context": self._extraer_contexto(doc_text, span_start, span_end)
                    })
                    
                    # Retornar el más cercano al "C/" (primera coincidencia válida)
                    break
        
        return resultados
    
    def _detectar_nombre_judicial_con_coma(self, doc) -> List[Dict[str, Any]]:
        """
        REGLA 6: Detecta nombres en formato judicial con coma: "APELLIDO, NOMBRE" (OPTIMIZADO).
        
        Ejemplo: "CARBALLO, MARTA" → extrae "CARBALLO, MARTA" (preservando la coma original)
        Formato común en expedientes judiciales argentinos.
        
        Args:
            doc: Documento procesado por spaCy
            
        Returns:
            Lista de matches con la estructura estándar
        """
        resultados = []
        doc_text = doc.text
        
        # OPTIMIZACIÓN: Usar regex pre-compilado a nivel de módulo
        for match in _PATRON_NOMBRE_COMA.finditer(doc_text):
            apellido = match.group(1)  # Parte antes de la coma
            nombre = match.group(2)    # Parte después de la coma
            
            # Verificar que cada parte tenga al menos 2 caracteres
            if len(apellido) < 2 or len(nombre) < 2:
                continue
            
            # Para validación, contar tokens sin la coma
            tokens_sin_coma = apellido.split() + nombre.split()
            
            # Validar cantidad total de tokens (2-6)
            if not (2 <= len(tokens_sin_coma) <= 6):
                continue
            
            span_start = match.start()
            span_end = match.end()
            
            # CAMBIO CLAVE: Retornar el nombre CON la coma original
            resultados.append({
                "rule": "NOMBRE_JUDICIAL_CON_COMA",
                "anchor": "coma_judicial",
                "matched_text": match.group(0),  # Con coma (original)
                "name_tokens": tokens_sin_coma,  # Tokens sin coma para procesamiento interno
                "nombre_original": f"{apellido}, {nombre}",  # Con coma preservada para output
                "span_start": span_start,
                "span_end": span_end,
                "context": self._extraer_contexto(doc_text, span_start, span_end)
            })
        
        return resultados
