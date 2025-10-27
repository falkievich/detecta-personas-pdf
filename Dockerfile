# syntax=docker/dockerfile:1
# Habilitar BuildKit para usar cache mounts

# Usar una imagen base de Python
FROM python:3.12-slim

# Establecer el directorio de trabajo
WORKDIR /app

# ====================
# CAPA 1: Dependencias de Python (SE CACHEA - solo se invalida si cambia requirements.txt)
# ====================
# Copiar SOLO requirements.txt primero (para aprovechar cache de Docker)
COPY requirements.txt .

# Instalar dependencias con cache mount de pip (persiste entre builds incluso si falla)
# IMPORTANTE: NO usar --no-cache-dir aquí para que se guarden los paquetes descargados
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    pip install --retries 10 --timeout 120 -r requirements.txt

# ====================
# CAPA 2: Código de la aplicación (se invalida con cada cambio de código)
# ====================
# Copiar el código de la aplicación AL FINAL
COPY . .

# Exponer el puerto en el que corre la aplicación
EXPOSE 8000

# Comando para ejecutar la aplicación
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
