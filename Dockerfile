# syntax=docker/dockerfile:1
# Habilitar BuildKit para usar cache mounts

# Usar una imagen base de Python
FROM python:3.12-slim

# Establecer el directorio de trabajo
WORKDIR /app

# ====================
# CAPA 1: Dependencias del sistema (SE CACHEA - rara vez cambia)
# ====================
# Usar cache mount para apt y agregar reintentos para manejar problemas de red/certificados
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=120 install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-spa \
    poppler-utils \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# ====================
# CAPA 2: Dependencias de Python (SE CACHEA - solo se invalida si cambia requirements.txt)
# ====================
# Copiar SOLO requirements.txt primero (para aprovechar cache de Docker)
COPY requirements.txt .

# Instalar dependencias con cache mount de pip (persiste entre builds incluso si falla)
# IMPORTANTE: NO usar --no-cache-dir aquí para que se guarden los paquetes descargados
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    pip install --retries 10 --timeout 120 -r requirements.txt

# Instalar transformers sin dependencias extra con cache
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    pip install --retries 10 --timeout 120 transformers --no-deps

# ====================
# CAPA 3: Pre-descarga del modelo de Hugging Face (OPCIONAL pero recomendado)
# ====================
# Descargar el modelo NER durante el build para evitar descargarlo en cada deploy
# Usa cache mount para Hugging Face (persiste modelos descargados entre builds)
RUN --mount=type=cache,target=/root/.cache/huggingface,sharing=locked \
    python -c "from transformers import pipeline; \
    pipeline('ner', model='mrm8488/bert-spanish-cased-finetuned-ner', aggregation_strategy='simple')" || true

# ====================
# CAPA 4: Código de la aplicación (se invalida con cada cambio de código)
# ====================
# Copiar el código de la aplicación AL FINAL
COPY . .

# Exponer el puerto en el que corre la aplicación
EXPOSE 8000

# Comando para ejecutar la aplicación
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
