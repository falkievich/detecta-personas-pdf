# PDF Matcher

Este proyecto ofrece dos funcionalidades complementarias para extraer y comparar datos en documentos PDF desde un backend, sin utilizar modelos de lenguaje (LLM). Ambas funciones están disponibles a través de endpoints HTTP (ver sección de API).

---

## Función 1 — Detectar Automáticamente Personas en un PDF

**Descripción**

- Permite subir un PDF al endpoint dedicado y, únicamente mediante procesamiento en backend (sin llamadas a modelos externos ni LLM), detectar y extraer:
  - Nombres y apellidos de personas físicas
  - Identificadores asociados: DNI, CUIL, CUIT, CUIF y Matrícula

**Cómo se usa (endpoint)**

- Endpoint principal: `POST /upload_files`
  - Campo `pdf_file`: archivo PDF (requerido)
  - Campo `data_file`: archivo opcional (`.json` o `.txt`) para la función de comparación (ver Función 2)

**Qué hace el backend para detectar personas**

1. **Normalización del texto extraído del PDF**:
   - Se extrae el texto página por página (PyMuPDF / fitz).
   - Se limpia el texto: eliminación de saltos de línea innecesarios, múltiples espacios y caracteres de separación.
   - Se aplican reglas simples de normalización: unificación de variantes (por ejemplo, "D.N.I." → "DNI"), eliminación de prefijos tipo `N°`, y limpieza de separadores de miles en números.

2. **Búsqueda basada en reglas y expresiones regulares**:
   - Se usan patrones regex para localizar etiquetas e identificadores (DNI, CUIL, CUIT, CUIF, Matrícula) y sus valores numéricos.
   - Para cada identificador encontrado, se toma una ventana de contexto anterior para intentar extraer el nombre asociado (1–5 palabras para personas físicas, ventanas más amplias para nombres jurídicos si hace falta).

3. **Agrupación y refinamiento**:
   - Se agrupan coincidencias por nombre e identificador para consolidar múltiples apariciones.
   - Se aplican heurísticas para fusionar entradas muy parecidas y evitar duplicados o fragmentaciones.

**Formato de salida (ejemplo)**

Al invocar `/upload_files` con solo el `pdf_file`, la respuesta JSON contendrá (ejemplo simplificado):

```json
{
  "comparison_performed": false,
  "comparison_result": null,
  "personas_identificadas_pdf": [
    {
      "nombre": "Juan Pérez",
      "identificadores": {
        "DNI": "12345678",
        "CUIL": null,
        "MATRICULA": null
      }
    },
    ...
  ]
}
```

**Notas importantes**

- Se prioriza la precisión en la extracción de identificadores numéricos y la asociación al nombre más probable en su ventana de contexto.

---

## Función 2 — Detectar Variables Seleccionadas en un PDF

**Descripción**

Esta función te permite **seleccionar específicamente** qué variables deseas extraer del PDF. A diferencia de la Función 1 (que detecta automáticamente personas completas con todos sus identificadores), aquí puedes elegir extraer solo nombres, solo DNI, solo CUIL, o cualquier combinación que necesites.

**Diferencias con la Función 1:**
- **Función 1**: Detecta automáticamente PERSONAS completas (nombre + apellido + todos los identificadores asociados). Usa endpoint `/upload_files` con lógica específica para detección integral de personas.
- **Función 2**: Tú eliges qué variables extraer (solo nombres, solo DNI, ambos, etc.). Usa endpoint diferente con lógica más granular y flexible.

**Cómo se usa (endpoint)**

- Endpoint: `POST /extraer_entidades`
  - Form data o JSON:
    - `pdf_file`: archivo PDF (requerido)
    - `entidades_solicitadas`: lista de variables a extraer

**Variables que puedes seleccionar:**

| Variable | Descripción | Validación |
|----------|-------------|------------|
| `nombre` o `nombres` | Personas físicas detectadas con pipeline de 6 fases | 6 reglas contextuales + filtros de limpieza |
| `dni` | 7-8 dígitos | Longitud + solo números |
| `cuil` | 11 dígitos (AA-BBBBBBBB-C) | Prefijos 20/23/24/27 + dígito verificador (módulo 11) |
| `cuit` | 11 dígitos (AA-BBBBBBBB-C) | Prefijos 20/23/24/27/30/33/34 + dígito verificador (módulo 11) |
| `cuif` | 1-10 dígitos | Solo números |
| `matricula` | 1-10 caracteres alfanuméricos | Solo letras y números |

**Ejemplos de uso:**

```json
// Extraer solo nombres
{
  "entidades_solicitadas": ["nombre"]
}

// Extraer solo DNI
{
  "entidades_solicitadas": ["dni"]
}

// Extraer nombres y DNI
{
  "entidades_solicitadas": ["nombre", "dni"]
}

// Extraer todos los identificadores (sin nombres)
{
  "entidades_solicitadas": ["dni", "cuil", "cuit", "cuif", "matricula"]
}

// Extraer solo CUIL y CUIT
{
  "entidades_solicitadas": ["cuil", "cuit"]
}
```

**Documentación Técnica del Pipeline de Extracción**

### Pipeline de Extracción de Nombres (6 Fases)

Cuando solicitas la variable `nombre`, se ejecuta un pipeline híbrido de 6 fases que combina expresiones regulares, NER de spaCy y reglas contextuales específicas para documentos judiciales argentinos:

```
TEXTO DEL PDF
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│  FASE 1: Captura con Regex                                  │
│  • PATRON_MAYUSCULAS: "GARCÍA LÓPEZ"                        │
│  • PATRON_MIXTO: "Juan Pérez"                               │
│  • PATRON_COMA: "CARBALLO, MARTA"                           │
└─────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│  FASE 2: Validación con spaCy NER                           │
│  • Valida candidatos contra entidades PER/PERSON            │
│  • Rechazados → pasan a Fase 3                              │
└─────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│  FASE 3: Reglas Contextuales (6 reglas)                     │
│  1. ANCLAS_CONTEXTUALES (señor, DNI, etc.)                  │
│  2. NOMBRE_DESPUES_DE_CONTRA                                │
│  3. PATRON_C_S (C/ nombre S/)                               │
│  4. APELLIDO_NOMBRE_JUDICIAL (Title Case)                   │
│  5. NOMBRE_ANTES_DE_C_BARRA                                 │
│  6. NOMBRE_JUDICIAL_CON_COMA                                │
└─────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│  FASE 4: Limpieza de Anclas                                 │
│  • Remueve: "señor", "doctor", "DNI", etc.                  │
│  • "señor Juan Pérez" → "Juan Pérez"                        │
└─────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│  FASE 5: Deduplicación y Limpieza de Bordes                 │
│  • Elimina duplicados y subconjuntos                        │
│  • Limpia preposiciones: "En Vallejos" → "Vallejos"         │
└─────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│  FASE 6: Filtro de Palabras No-Nombres                      │
│  • Elimina: "Juzgado", "Tribunal", "Corte", etc.           │
└─────────────────────────────────────────────────────────────┘
     │
     ▼
NOMBRES FINALES VALIDADOS
```

**Detalle de las 6 Reglas Contextuales:**

1. **ANCLAS_CONTEXTUALES**: Detecta nombres cerca de palabras-cue con direccionalidad
   - DERECHA: Palabras como "ciudadano", "señor", "doctor" → busca nombre a la derecha
   - IZQUIERDA: Palabras como "DNI", "CUIL", "documento" → busca nombre a la izquierda

2. **NOMBRE_DESPUES_DE_CONTRA**: Detecta nombres después de "contra" en expedientes judiciales
   - Patrón: "contra" + 2-6 tokens en MAYÚSCULAS (mínimo 2 caracteres por token)

3. **PATRON_C_S**: Detecta nombres entre "C/" y "S/" (formato expediente judicial argentino)
   - Formato: "C/ NOMBRE S/"

4. **APELLIDO_NOMBRE_JUDICIAL**: Detecta formato Title Case judicial
   - Patrón: 2-6 tokens en Title Case (ej: "Codazzi Luis", "Daniel Ernesto D'Avis")
   - Mínimo 2 caracteres por token para evitar acrónimos

5. **NOMBRE_ANTES_DE_C_BARRA**: Detecta nombres antes de "C/" (demandante en formato judicial)
   - Patrón: NOMBRE + "C/"

6. **NOMBRE_JUDICIAL_CON_COMA**: Detecta formato "APELLIDO, NOMBRE" (judicial argentino)
   - Usa regex: `([A-Z]{2,}(?:\s+[A-Z]{2,}){0,2}),\s+([A-Z]{2,}(?:\s+[A-Z]{2,}){0,2})`

### Extracción y Validación de Documentos

Cuando solicitas variables de tipo documento (`dni`, `cuil`, `cuit`, `cuif`, `matricula`), se aplica el siguiente proceso:

```
TEXTO NORMALIZADO DEL PDF
     │
     ▼
┌──────────────────────────────────────────────────────────────┐
│  Detección con Regex + Validación Estricta                   │
├──────────────────────────────────────────────────────────────┤
│  DNI      → 7-8 dígitos                                      │
│  CUIL     → 11 dígitos + prefijo + dígito verificador       │
│  CUIT     → 11 dígitos + prefijo + dígito verificador       │
│  CUIF     → 1-10 dígitos                                     │
│  Matrícula → 1-10 alfanuméricos                              │
└──────────────────────────────────────────────────────────────┘
     │
     ▼
DOCUMENTOS VALIDADOS
```

**Validadores implementados:**

- **DNI**: `validar_dni()` - Verifica longitud (7-8 dígitos) y que sean solo números
- **CUIL**: `validar_cuil()` - Verifica longitud (11 dígitos), prefijos válidos (20/23/24/27) y dígito verificador con algoritmo módulo 11
- **CUIT**: `validar_cuit()` - Verifica longitud (11 dígitos), prefijos válidos (20/23/24/27/30/33/34) y dígito verificador con algoritmo módulo 11
- **CUIF**: `validar_cuif()` - Verifica longitud (1-10 dígitos) y que sean solo números
- **Matrícula**: `validar_matricula()` - Verifica longitud (1-10 caracteres) y que sean solo alfanuméricos

**Algoritmo de Validación del Dígito Verificador (CUIL/CUIT):**

El dígito verificador se calcula usando el algoritmo de módulo 11:
1. Se multiplican los primeros 10 dígitos por la secuencia: `[5, 4, 3, 2, 7, 6, 5, 4, 3, 2]`
2. Se suma el resultado de las multiplicaciones
3. Se calcula el resto de dividir la suma entre 11
4. El dígito verificador es `11 - resto`
5. Casos especiales:
   - Si resultado = 11 → dígito verificador = 0
   - Si resultado = 10 → dígito verificador = 9

Ejemplo: CUIL `20-12345678-X`
```
Dígitos: 2 0 1 2 3 4 5 6 7 8
Multiplicadores: 5 4 3 2 7 6 5 4 3 2
Productos: 10+0+3+4+21+24+25+24+21+16 = 148
Resto: 148 % 11 = 5
Dígito verificador: 11 - 5 = 6
```

**Ejemplo práctico completo:**

Texto del PDF:
```
En la ciudad de Buenos Aires, se presenta el ciudadano GARCÍA LÓPEZ JUAN CARLOS 
DNI 12345678 CUIL 20-12345678-1 en contra de PÉREZ MARTÍNEZ MARÍA FERNANDA.
El Dr. Codazzi Luis, matrícula MP987654, representa al demandante.
```

Solicitud: `{"entidades_solicitadas": ["nombre", "dni", "cuil", "matricula"]}`

Respuesta:
```json
{
  "nombres": [
    {
      "nombre": "García López Juan Carlos",
      "contexto": "...ciudadano GARCÍA LÓPEZ JUAN CARLOS DNI..."
    },
    {
      "nombre": "Pérez Martínez María Fernanda",
      "contexto": "...contra PÉREZ MARTÍNEZ MARÍA FERNANDA..."
    },
    {
      "nombre": "Codazzi Luis",
      "contexto": "...Dr. Codazzi Luis, matrícula..."
    }
  ],
  "dni": [
    {
      "valor": "12345678",
      "contexto": "...DNI 12345678 CUIL..."
    }
  ],
  "cuil": [
    {
      "valor": "20-12345678-1",
      "contexto": "...CUIL 20-12345678-1 en..."
    }
  ],
  "matricula": [
    {
      "valor": "MP987654",
      "contexto": "...matrícula MP987654, representa..."
    }
  ]
}
```

---

## Función 3 — Comparar PDF con `.json` / `.txt`

**Descripción**

- Al endpoint `POST /upload_files` (Función 1) puedes adjuntar opcionalmente un archivo de datos (`.json` o `.txt`) junto con el PDF.
- El sistema extrae la información del PDF automáticamente (como en la Función 1) y compara los valores provistos en el `.json/.txt` con los valores extraídos del PDF.
- Para cada par valor objetivo (del .json/.txt) vs candidato (del PDF), se calcula una puntuación de similitud y se clasifica en una de 4 categorías: `exacta`, `alta`, `media`, `baja`.

**Entrada esperada (ejemplo JSON)**

```json
{
  "nombre_apellido": "Juan Perez",
  "DNI": "12345678",
  "CUIT": "20-12345678-1"
}
```

**Cómo se realiza la comparación**

1. **Normalización previa**:
   - Ambos lados (valor objetivo y candidatos extraídos) se normalizan: minúsculas, eliminación de tildes y caracteres no significativos, limpieza de espacios y formato de números.

2. **Estrategias de comparación según tipo de dato**:
   - Identificadores numéricos (DNI, CUIL, CUIT, CUIF, Matrícula): se prioriza la comparación numérica/exacta y formatos equivalentes (puntos, guiones ignorados). Coincidencias exactamente iguales reciben la puntuación más alta.
   - Textos (nombres): se usan métricas de similitud de cadenas (p. ej. ratio de edición/token-similarity). También se consideran coincidencias parciales y orden de tokens.

3. **Cálculo de la puntuación y mapeo a categorías**

- Se obtiene una puntuación normalizada en rango 0–100.
- Umbrales por defecto (configurables):
  - exacta: >= 90
  - alta: 70–89
  - media: 40–69
  - baja: < 40

**Salida del comparador (ejemplo)**

Al enviar `data_file` junto al `pdf_file`, la respuesta incluirá `comparison_performed: true` y un objeto `comparison_result` con una lista de comparaciones:

```json
{
  "comparison_performed": true,
  "comparison_result": [
    {
      "field": "nombre_apellido",
      "value_from_file": "Juan Perez",
      "best_match_in_pdf": "Juan Pérez",
      "score": 95,
      "category": "exacta"
    },
    {
      "field": "DNI",
      "value_from_file": "12345678",
      "best_match_in_pdf": "12345678",
      "score": 100,
      "category": "exacta"
    },
    {
      "field": "CUIT",
      "value_from_file": "20-12345678-1",
      "best_match_in_pdf": "20123456781",
      "score": 85,
      "category": "alta"
    }
  ],
  "personas_identificadas_pdf": [ ... ]
}
```

**Explicación práctica**

- Para cada campo del `.json/.txt` el servicio devuelve cuál es el mejor candidato encontrado en el PDF, la puntuación (0–100) y la categoría de coincidencia.
- Esto permite automatizar verificaciones (ej. validar que el DNI del documento coincide con la base de datos) y obtener una confianza cuantificada sobre cada coincidencia.

---

## API y uso rápido

### Endpoints principales

**Función 1 - Detectar Personas Automáticamente:**
- `POST /upload_files`
  - Form data:
    - `pdf_file` (file, requerido): PDF a analizar
    - `data_file` (file, opcional): `.json` o `.txt` con los valores a comparar (activa Función 3)
  - Respuesta: JSON con `personas_identificadas_pdf` (personas completas con todos sus identificadores)
  - Si se envía `data_file`, también incluye `comparison_result` (Función 3)

**Función 2 - Detectar Variables Seleccionadas:**
- `POST /extraer_entidades`
  - Form data o Body JSON:
    - `pdf_file`: archivo PDF (requerido)
    - `entidades_solicitadas`: array de strings (ej: `["nombre", "dni"]`)
  - Respuesta: JSON con solo las entidades solicitadas
  - Ejemplo: si solicitas `["nombre"]`, solo recibes nombres (sin identificadores)

**Función 3 - Comparar:**
- Se activa automáticamente en `POST /upload_files` al enviar `data_file`
  - Compara los valores del archivo `.json/.txt` con los extraídos del PDF
  - Retorna puntuaciones y categorías de similitud para cada campo

**Endpoints auxiliares:**
- `POST /detect_phrase`
  - Body JSON: `{ "text": "<frase o párrafo>" }`
  - Útil para detectar nombre + identificador dentro de un texto sin subir un PDF

Nota: los endpoints están implementados con FastAPI. Al desplegar la aplicación con Docker (o ejecutar localmente con Uvicorn), FastAPI genera documentación automática accesible en:

```
http://localhost:8000/docs
```
---

## Construcción con Docker y BuildKit

Este proyecto usa Docker con BuildKit habilitado para optimizar tiempos de build y mantener imágenes más limpias. Esto permite:

- Ejecución paralela de pasos independientes.
- Cachés persistentes para `pip` mediante `--mount=type=cache`, evitando descargas repetidas entre builds.
- Montajes temporales que no se copian a la imagen final, reduciendo el tamaño de la imagen resultante.
- Soporte para reintentos y timeouts en descargas, lo que hace los builds más estables en redes inestables o con restricciones.

Está organizado para maximizar el uso del caché y mantener la imagen lo más ligera posible:

1. Dependencias de Python (instaladas desde `requirements.txt`).
2. Código de la aplicación (se copia al final para evitar invalidar la cache de dependencias cuando solo cambia el código).

Pasos para construir y desplegar:

1) Reconstruir la imagen:

    **Windows (con BuildKit habilitado)**
   
   .\build.ps1

   **Manualmente**

   docker-compose build --progress=plain

2) Levantar el contenedor con la imagen ya construida:

   docker-compose up -d

3) Acceder a la API:

   http://127.0.0.1:8000

Notas rápidas:
- Si un paso de instalación falla por certificados o red, vuelve a ejecutar `.\build.ps1`; gracias a los caches, lo ya descargado o instalado no se volverá a bajar.
- Si solo cambias código (no `requirements.txt` ni dependencias del sistema), no es necesario reconstruir la imagen: basta con `docker-compose up -d` para levantar el servicio.



- **Privacidad**: todo el procesamiento se realiza en el servidor que ejecuta la aplicación; no se envía contenido a servicios externos por defecto.
