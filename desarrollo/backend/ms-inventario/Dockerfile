FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias primero (aprovecha cache de capas de Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el codigo de la aplicacion
COPY app ./app

# El Security Group "sg-backend" (infra/terraform/etapa_2) abre el puerto 8080
EXPOSE 8080

# Variables de entorno (DATABASE_URL, AZURE_TENANT_ID, AZURE_CLIENT_ID) se inyectan
# en tiempo de ejecucion (docker run --env-file .env / ECS task definition), nunca
# se hornean dentro de la imagen.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
