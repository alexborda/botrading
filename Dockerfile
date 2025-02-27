# Etapa 1: Backend FastAPI
FROM python:3.13.1 AS backend-builder
WORKDIR /backend

# Copiar solo los archivos necesarios primero (para aprovechar caché de Docker)
COPY requirements.txt ./
RUN python -m venv /backend/.venv
RUN /backend/.venv/bin/pip install --upgrade pip && /backend/.venv/bin/pip install -r requirements.txt

# Copiar el código del backend
COPY main.py ./

# Etapa 2: Construcción del frontend (Vite + Preact)
FROM node:22.13.1 AS frontend-builder
WORKDIR /frontend
COPY package.json package-lock.json ./
RUN npm install
COPY src ./
RUN npm run build

# Etapa 3: Contenedor final con Nginx y FastAPI
FROM nginx:alpine

# 🔥 CORRECCIÓN: Instalar solo `python3` y `py3-pip` (sin `python3-virtualenv`)
RUN apk add --no-cache python3 py3-pip 

WORKDIR /backend
COPY --from=backend-builder /backend /backend
COPY --from=frontend-builder /frontend/dist /usr/share/nginx/html

# 🔥 CORRECCIÓN: Crear el entorno virtual de forma explícita
RUN python3 -m venv /backend/.venv
RUN /backend/.venv/bin/pip install --upgrade pip
RUN /backend/.venv/bin/pip install --no-cache-dir -r /backend/requirements.txt

# Copiar configuración de Nginx
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80 8000

# Ejecutar FastAPI y Nginx
CMD ["sh", "-c", "/backend/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 & nginx -g 'daemon off;'"]
