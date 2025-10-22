# Fuzzy PDF Matcher

Este programa ofrece dos funcionalidades principales, 1. Permite la extracción y comparación de información de documentos PDF mediante el uso de la lógica difusa. 2. Permite la detección automática de datos pertenecientes a personas y organizaciones.

---

## 1. Búsqueda fuzzy de términos en PDF

- **Descripción**  
  Mediante una API, puedes enviar un `.pdf` y un archivo de datos (`.json` o `.txt`) que contenga los valores que quieres buscar, por ejemplo:  
  ```json
  { "nombre_apellido": "thiago" }

- **Cómo funciona** 
  1. Se extraen del PDF los textos candidatos.

  2. Se compara cada candidato contra el valor objetivo usando lógica difusa (triangular membership functions: baja, media, alta, exacta).

  3. Se realiza inferencia y defuzzificación (centro de gravedad) para obtener un “valor crisp” de similitud.

  4. Se devuelven las palabras o conjuntos de palabras del PDF que más se parecen a los valores del .json/.txt.

---
## 2. Detección automática de datos de personas y organizaciones
  Este módulo se encarga de extraer y clasificar información de identificación tanto de personas físicas como de organizaciones (personas juridicas) en un texto o PDF. Se divide en dos etapas principales:

* **Normalización del texto**  
* **Búsqueda y agrupación de patrones de identificación**

---

### 2.1 Normalización de texto de PDF

- **Archivo**: `extraer_texto_pdf.py`  
- **Qué hace**:  
  1. Abre y recorre todas las páginas de un PDF con PyMuPDF (`fitz`).  
  2. Concatena el texto extraído y elimina saltos de línea, retornos de carro y espacios múltiples.  
  3. En la versión avanzada, además unifica sinónimos (`Documento` → `DNI`, variantes de “D.N.I.” → `DNI`, “M.P.” → `MATRICULA`), quita prefijos como `N°` delante de números y elimina separadores de miles.  
  4. Devuelve una sola línea de texto limpia, lista para el siguiente paso.

---

### 2.2 Detección de personas físicas y organizaciones

- **Archivo**: `detectar_personas_pdf.py`  
- **Qué hace**:  
  1. Llama a la función de normalización avanzada para obtener el texto limpio (desde un PDF o texto plano).  
  2. Define patrones regex para cada etiqueta de identificación (`DNI`, `MATRICULA`, `CUIF`, `CUIT`, `CUIL`).  
  3. Busca números asociados a esas etiquetas y extrae el nombre previo usando ventanas de contexto y patrones de nombre “natural” (1–3 palabras) o “jurídico” (hasta 7 palabras con puntos y &).  
  4. Agrupa coincidencias por nombre y etiqueta, refina los casos de solo CUIT usando el patrón jurídico, y fusiona entradas muy parecidas para evitar duplicados.  
  5. Devuelve una lista de resultados en formato  
     ```
     Nombre Apellido | DNI N° xxx | CUIT N° yyy | …
     ``` 
