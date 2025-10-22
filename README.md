# PDF Matcher

Este proyecto ofrece dos funcionalidades complementarias para extraer y comparar datos en documentos PDF desde un backend, sin utilizar modelos de lenguaje (LLM). Ambas funciones están disponibles a través de endpoints HTTP (ver sección de API).

---

## Función 1 — Detectar Personas en un PDF

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
   - Para cada identificador encontrado, se toma una ventana de contexto anterior para intentar extraer el nombre asociado (1–3 palabras para personas físicas, ventanas más amplias para nombres jurídicos si hace falta).

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

- Este módulo no depende de modelos de lenguaje; la extracción se basa en normalización, regex y reglas heurísticas.
- Se prioriza la precisión en la extracción de identificadores numéricos y la asociación al nombre más probable en su ventana de contexto.

---

## Función 2 — Comparar PDF con `.json` / `.txt`

**Descripción**

- Al mismo endpoint `POST /upload_files` puedes adjuntar opcionalmente un archivo de datos (`.json` o `.txt`) junto con el PDF.
- El sistema extrae la información del PDF (como en la Función 1) y compara los valores provistos en el `.json/.txt` con los valores extraídos del PDF.
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

- `POST /upload_files` (principal)
  - Form data:
    - `pdf_file` (file, requerido): PDF a analizar
    - `data_file` (file, opcional): `.json` o `.txt` con los valores a comparar
  - Respuesta: JSON con `personas_identificadas_pdf` y, si se suministró `data_file`, `comparison_result`.

- `POST /detect_phrase` (auxiliar)
  - Body JSON: `{ "text": "<frase o párrafo>" }`
  - Útil para detectar nombre + identificador dentro de un texto sin subir un PDF.

---

## Consideraciones finales

- **Privacidad**: todo el procesamiento se realiza en el servidor que ejecuta la aplicación; no se envía contenido a servicios externos por defecto.
- **Reproducibilidad**: se recomienda fijar versiones en `requirements.txt` para entornos de producción. Después de instalar las dependencias listadas con `pip install -r requirements.txt`, si en algún momento decides instalar `transformers` y quieres evitar que pip descargue e instale todas las dependencias adicionales de ese paquete, instálalo manualmente con:

```
pip install transformers --no-deps
```

Nota: usar `--no-deps` evita la instalación automática de dependencias. Si necesitas algunas dependencias concretas de `transformers` (por ejemplo `torch`, `tokenizers`, `huggingface-hub`, `safetensors`, etc.), añádelas explícitamente en `requirements.txt` o instálalas manualmente después.

Tesseract-OCR (Windows)

- `pytesseract` es solo un wrapper en Python; necesitás tener el programa Tesseract-OCR instalado en tu sistema para que `pytesseract` funcione.

Instalar Tesseract-OCR en Windows:

1. Descargá el instalador desde:
   https://github.com/UB-Mannheim/tesseract/wiki
   (buscá el archivo .exe, por ejemplo `tesseract-ocr-w64-setup-5.x.x.exe`).

2. Durante la instalación:
   - Activá la opción “Add Tesseract to the system path” para poder usar `tesseract` desde cualquier terminal.

3. Verificá que funcione ejecutando en una terminal nueva:

```
tesseract --version
```

4. Si no activaste “Add to PATH” durante la instalación, agregá la ruta manualmente en las Variables de entorno de Windows:
   - Panel de control → Sistema → Configuración avanzada del sistema → Variables de entorno
   - En Variables del sistema, editá `Path` y agregá la ruta de instalación, por ejemplo:

```
C:\Program Files\Tesseract-OCR\
```

5. Guardá los cambios, cerrá ventanas abiertas y abrí una nueva terminal. Verificá nuevamente con:

```
tesseract --version
```

De esta forma, Tesseract quedará disponible globalmente y `pytesseract` podrá invocar el ejecutable sin configuraciones adicionales en el código.

---
