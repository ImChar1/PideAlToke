FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1
# Instalar dependencias primero (aprovecha cache de capas de Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar SOLO el codigo de la aplicacion (nada de .env, bases locales ni tests)
COPY app ./app

# El contenedor escucha en el 8000; docker-compose / Terraform lo publican en 8001-8004
EXPOSE 8000

# Variables de entorno (DATABASE_URL, AZURE_TENANT_ID, AZURE_CLIENT_ID, ...) se inyectan
# en tiempo de ejecucion (docker compose / Terraform), nunca se hornean dentro de la imagen.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
