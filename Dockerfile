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

# Copiar los archivos estáticos del frontend al contenedor de Nginx
COPY --from=frontend-builder /app/dist /usr/share/nginx/html

# Copiar la aplicación del backend FastAPI al contenedor
COPY --from=backend-builder /app /app

# Instalar Python y pip en la imagen final
RUN apk add --no-cache python3 py3-pip

# Instalar dependencias directamente sin entorno virtual
RUN pip install --no-cache-dir -r /app/requirements.txt

# Configurar Nginx
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/nginx.conf

# Exponer los puertos
EXPOSE 80
EXPOSE 8000

# Comando para iniciar tanto el servidor de FastAPI como Nginx
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port 8000 & nginx -g 'daemon off;'"]
