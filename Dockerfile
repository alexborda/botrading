# ---------------------------
# Etapa 1: Construcción del Frontend (Preact/Vite)
# ---------------------------
    FROM node:22.13.1 AS frontend-builder
    WORKDIR /build-frontend
    
    # Copiar archivos necesarios para el build del frontend
    COPY package.json package-lock.json ./
        
    # Instalar dependencias y construir el frontend
    RUN npm install --frozen-lockfile

    # Copiar el resto de los archivos necesarios para el build
    COPY . . 

    # Forzar el build y verificar si `dist/` se crea
    RUN npm run build || (echo "⚠️ ERROR: Falló el build del frontend" && exit 1)
    
    # ---------------------------
    # Etapa 2: Construcción del Backend (FastAPI)
    # ---------------------------
    FROM python:3.13.1 AS backend-builder
    WORKDIR /build-backend
    
    # Copiar los archivos necesarios para el backend (están en la raíz)
    COPY requirements.txt main.py ./
    
    # Crear un entorno virtual e instalar las dependencias
    RUN python -m venv .venv && \
        .venv/bin/pip install --upgrade pip && \
        .venv/bin/pip install --no-cache-dir -r requirements.txt
    
    # ---------------------------
    # Etapa 3: Imagen Final (Nginx + FastAPI)
    # ---------------------------
    FROM nginx:alpine AS final
    WORKDIR /final
    
    # Instalar Python3 y pip en la imagen final (Nginx:alpine es muy ligera)
    RUN apk add --no-cache python3 py3-pip
    
   # Copiar el frontend construido en la imagen final
    COPY --from=frontend-builder /build-frontend/dist /usr/share/nginx/html

    # Asegurar que la carpeta exista
    RUN ls -lah /usr/share/nginx/html || (echo "⚠️ ERROR: No se copiaron los archivos del frontend" && exit 1)

        
    # Recrear el entorno virtual en la imagen final para asegurar compatibilidad
    RUN python3 -m venv /final/backend/.venv && \
        /final/backend/.venv/bin/pip install --upgrade pip && \
        /final/backend/.venv/bin/pip install --no-cache-dir -r /final/backend/requirements.txt
    
    # Copiar el frontend construido desde la etapa 1 al directorio que Nginx sirve
    COPY --from=frontend-builder /build-frontend/dist/ /usr/share/nginx/html
    
    # Copiar la configuración personalizada de Nginx (si tienes nginx.conf en la raíz)
    COPY nginx.conf /etc/nginx/nginx.conf
    
    # Exponer puertos: 80 para Nginx y 8000 para el backend
    EXPOSE 80
    EXPOSE 8000
    
    # Ejecutar el backend (Uvicorn) en segundo plano y luego iniciar Nginx
    CMD ["sh", "-c", "/final/backend/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 & nginx -g 'daemon off;'"]
    