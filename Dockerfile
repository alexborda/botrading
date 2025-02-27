# Etapa 1: Usar una imagen base de Python más completa
FROM python:3.13.1 AS backend-builder

# Establecer variables de entorno
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

# Crear entorno virtual
RUN python -m venv .venv
COPY requirements.txt ./
RUN .venv/bin/pip install --upgrade pip && .venv/bin/pip install -r requirements.txt

# Etapa 2: Construcción del frontend (Vite)
ARG NODE_VERSION=22.13.1
FROM node:22.13.1 AS frontend-builder

LABEL fly_launch_runtime="Vite"

WORKDIR /app

ENV NODE_ENV="production"

# Instalar paquetes necesarios
RUN apt-get update -qq && \
    apt-get install --no-install-recommends -y build-essential node-gyp pkg-config python-is-python3

COPY package-lock.json package.json ./
RUN npm ci --include=dev

COPY . .
RUN npm run build
RUN npm prune --omit=dev

# Etapa 3: Configurar el contenedor final con Nginx y FastAPI
FROM nginx:alpine

# Instalar Python y pip en Alpine Linux
RUN apk add --no-cache python3 py3-pip

# Copiar la aplicación del backend desde la Etapa 1
COPY --from=backend-builder /app /app

# Crear un entorno virtual dentro del contenedor final
RUN python3 -m venv /app/.venv

# Activar el entorno virtual e instalar dependencias
RUN /app/.venv/bin/pip install --upgrade pip
RUN /app/.venv/bin/pip install --no-cache-dir -r /app/requirements.txt

# Configurar Nginx
COPY nginx.conf /etc/nginx/nginx.conf

# Exponer los puertos
EXPOSE 80
EXPOSE 8000

# Ejecutar FastAPI dentro del entorno virtual
CMD ["sh", "-c", "/app/.venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000 & nginx -g 'daemon off;'"]
