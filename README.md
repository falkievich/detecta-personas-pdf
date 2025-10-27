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

   .\build.ps1

2) Levantar el contenedor con la imagen ya construida:

   docker-compose up -d

3) Acceder a la API:

   http://127.0.0.1:8000

Notas rápidas:
- Si un paso de instalación falla por certificados o red, vuelve a ejecutar `.\build.ps1`; gracias a los caches, lo ya descargado o instalado no se volverá a bajar.
- Si solo cambias código (no `requirements.txt` ni dependencias del sistema), no es necesario reconstruir la imagen: basta con `docker-compose up -d` para levantar el servicio.



- **Privacidad**: todo el procesamiento se realiza en el servidor que ejecuta la aplicación; no se envía contenido a servicios externos por defecto.
