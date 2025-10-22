import re
from collections import defaultdict
from funcs.normalizacion.normalizar_y_extraer_texto_pdf import normalizacion_avanzada_pdf, detectar_pdf_escaneado

def detectar_personas_dni_matricula(path_pdf: str = None, raw_text: str = None):
    """
    Extrae y normaliza el texto de un PDF (normalizacion_avanzada_pdf), luego detecta pares
    Nombre + DNI y Nombre + Matrícula (ambos casos pueden tener CUIF, CUIT e CUIL) usando patrones adaptados
    al texto preprocesado.
    """
    # 1) Obtener texto normalizado
    if raw_text is not None:
        texto = normalizacion_avanzada_pdf(raw_text=raw_text)
    elif path_pdf:
        _, texto = detectar_pdf_escaneado(path_pdf=path_pdf)
    else:
        raise ValueError("Se debe pasar path_pdf o raw_text")
    
    #print("texto pdf: ", texto)

    # 2) Mapear cada etiqueta a su regex de número
    doc_patterns = {
        "DNI":      r'\bDNI\s+(\d+)\b',
        "MATRICULA":r'\bMATRICULA\s+(\d+)\b',
        "CUIF":     r'\bCUIF\s+(\d+)\b',
        "CUIT":     r'\bCUIT\s+(\d+)\b',
        "CUIL":     r'\bCUIL\s+(\d+)\b',
    }

    # 3) Patrón de nombre: mínimo 1 palabra que empiecen en mayúscula, máximo 6 (la palabra iniclal (1) + 5 más que cumplan los requisitos)
    name_pat_natural = re.compile(
        r'\b([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ]+'
        r'(?:\s+[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ]+){1,5})\b'
    )

    window_natural  = 100  # caracteres hacia atrás desde el inicio del match

    # 4) Patrón de nombre “jurídico”: hasta 7 palabras, admitiendo puntos y & en cada token
    name_pat_juridico = re.compile(
        r'\b('
        r'[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ\.\&]+'              # primera “palabra” con letras, puntos o &
        r'(?:\s+[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ\.\&]+){1,7}'  # de 1 a 7 palabras adicionales iguales
        r')\b'
    )
    window_juridico = 70

    # Extrae el último nombre que coincide con name_pattern dentro de los window_size caracteres anteriores a idx
    def extraer_nombre(idx: int, name_pattern: re.Pattern, window_size: int) -> str:
        start = max(0, idx - window_size)
        segmento = texto[start:idx]
        matches = name_pattern.findall(segmento)
        return matches[-1] if matches else ""

    # 5) Stop-words
    STOP_WORDS = {
        # Documentos / etiquetas
        "dni", "matricula", "mp", "cuif", "cuit", "cuil",
        
        # Tratamientos y títulos
        "señor", "señora", "sr", "sra", "srta", "juez", "jueza",
        "ciudadano", "ciudadana",
        "doctor", "doctora", "dr", "dra", "drs", "dras", "dr.", "dra.", "drs.", "dras.",
        "abogado", "abogada", "letrado", "letrada",
        
        # Palabras comunes que no deben formar parte del nombre
        "que", "heredero", "heredera", "nacimiento", "partida"
    }

    # 6) Primer pase: detección “natural” para todas las etiquetas
    raw_grouped = defaultdict(list)  # raw_name -> [ "DNI N° xxx", ... ]
    for etiqueta, pat in doc_patterns.items():
        regex = re.compile(pat, flags=re.IGNORECASE)
        for m in regex.finditer(texto):
            num = m.group(1)
            # usar patrón natural
            raw_name = extraer_nombre(m.start(), name_pat_natural, window_natural)
            if not raw_name:
                continue
            # filtrar stop-words
            tokens = [t for t in raw_name.split() if t.lower() not in STOP_WORDS]
            if len(tokens) < 2:
                continue
            clean_name = " ".join(tokens)
            clave = f"{etiqueta} N° {num}"

            if clave not in raw_grouped[clean_name]:
                # Evitar duplicados del mismo tipo de documento
                tipos_existentes = {t.split()[0] for t in raw_grouped[clean_name]}
                if etiqueta not in tipos_existentes:
                    raw_grouped[clean_name].append(clave)

                # --- Buscar documentos extra hacia adelante (sin truncar, con límite de distancia) ---
                tail = texto[m.end():]  # NO recortamos a 70 para no truncar números. Si llega a 70 caracteres y detectó un número, este lo obtendrá entero a pesar de que supere el límite establecido
                for other_label, other_pat in doc_patterns.items():
                    if other_label == etiqueta:
                        continue  # evitar duplicar el mismo tipo

                    regex2 = re.compile(other_pat, flags=re.IGNORECASE)
                    m2 = regex2.search(tail)
                    if not m2:
                        continue

                    # 1) Respetar tu ventana de 70: solo aceptar si el doc está a <= 70 chars
                    if m2.start() > 70:
                        continue

                    # 2) Si entre el doc actual y el próximo aparece un posible nombre, no asociar
                    segmento_entre = tail[:m2.start()]
                    if re.search(r'\b[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ]+){1,3}\b', segmento_entre):
                        continue

                    # 3) Extraer número (y limpiar separadores si es CUIT/CUIL)
                    num2 = m2.group(1)
                    if other_label in ("CUIT", "CUIL"):
                        num2 = re.sub(r'\D', '', num2)

                    clave2 = f"{other_label} N° {num2}"

                    # 4) Evitar duplicados del mismo tipo de documento para la misma persona
                    if clave2 not in raw_grouped[clean_name]:
                        tipos_existentes = {t.split()[0] for t in raw_grouped[clean_name]}
                        if other_label not in tipos_existentes:
                            raw_grouped[clean_name].append(clave2)

    # 7) Segundo pase: rehacer nombres para entradas SOLO CUIT (Pensado para Nombres de Empresas)
    for name, tags in list(raw_grouped.items()):
        # comprobar si solo tiene CUIT
        if len(tags) == 1 and tags[0].upper().startswith("CUIT "):
            # extraer el número
            num = tags[0].split("N°")[1].strip()
            # buscar la posición de CUIT num en el texto
            pat_cuit = re.compile(r'\bCUIT\s+' + re.escape(num) + r'\b', flags=re.IGNORECASE)
            m = pat_cuit.search(texto)
            if m:
                # extraer nombre con ventana reducida y patrón jurídico
                new_raw = extraer_nombre(m.start(), name_pat_juridico, window_juridico)
                if new_raw:
                    tokens = [t for t in new_raw.split() if t.lower() not in STOP_WORDS]
                    if len(tokens) >= 2:
                        new_clean = " ".join(tokens)
                        # reasignar tags al nuevo nombre
                        raw_grouped[new_clean] = raw_grouped.pop(name)

    # 8) Agrupación por subconjunto de tokens (tolerancia k=1)
    k = 1
    merged = []
    for raw_name, tags in raw_grouped.items():
        toks = set(raw_name.lower().split())
        placed = False

        for entry in merged:
            existing = entry['tokens']
            # nuevo ⊆ existente? - Si toks es subconjunto de existing con diferencia <= k
            if toks <= existing and len(existing) - len(toks) <= k:
                entry['tags'] += [t for t in tags if t not in entry['tags']]
                placed = True
                break
            # existente ⊆ nuevo? - Si existing es subconjunto de new con diferencia <= k
            if existing <= toks and len(toks) - len(existing) <= k:
                entry['tokens'] = toks
                entry['name']   = raw_name
                entry['tags']   = list(set(entry['tags'] + tags))
                placed = True
                break

        if not placed:
            merged.append({'tokens': toks, 'name': raw_name, 'tags': list(tags)})

    # 9) Formatear resultado preliminar
    resultado = []
    for e in merged:
        resultado.append(f"{e['name'].title()} | " + " | ".join(e['tags']))

    # 10) Consolidación final de personas duplicadas:
    # Si varias entradas comparten el mismo documento (DNI, CUIT, CUIL, etc.),
    # se fusionan en una sola, priorizando el nombre más largo y combinando todas las etiquetas.

    final_result = []
    seen_docs = {}

    for e in merged:
        name = e['name'].strip()
        # Buscar todos los documentos en las etiquetas
        doc_keys = set(re.findall(
            r'(DNI|MATRICULA|CUIT|CUIL|CUIF)\s+N°\s*(\d+)',
            " ".join(e['tags']),
            flags=re.IGNORECASE
        ))

        duplicate_of = None
        for doc_type, num in doc_keys:
            if (doc_type, num) in seen_docs:
                duplicate_of = seen_docs[(doc_type, num)]
                break

        if duplicate_of:
            # Fusionar con el existente si es más completo
            existing = next((r for r in final_result if r['name'] == duplicate_of), None)
            if existing:
                # Priorizar el nombre más largo
                if len(name.split()) > len(existing['name'].split()):
                    existing['name'] = name.title()
                # Agregar etiquetas nuevas si hay
                for t in e['tags']:
                    if t not in existing['tags']:
                        existing['tags'].append(t)
        else:
            # Registrar nuevo
            final_result.append({'name': name.title(), 'tags': e['tags']})
            for doc_type, num in doc_keys:
                seen_docs[(doc_type, num)] = name

    # 11) Reconstruir formato de salida limpio y ordenado
    resultado = [
        f"{r['name']} | " + " | ".join(sorted(r['tags'], key=lambda x: ('DNI' not in x, 'MATRICULA' not in x)))
        for r in final_result
    ]

    return resultado