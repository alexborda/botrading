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
    
    # Copiar la carpeta backend completa (¡incluyendo requirements.txt dentro!)
    COPY backend /build-backend/
    
    # Establecer el directorio de trabajo DENTRO de la carpeta backend en el builder
    WORKDIR /build-backend/backend
    
    # Crear un entorno virtual e instalar las dependencias (ahora requirements.txt está en la carpeta backend)
    RUN python -m venv .venv && \
        .venv/bin/pip install --upgrade pip && \
        .venv/bin/pip install --no-cache-dir -r requirements.txt
    # ---------------------------
    # Etapa 3: Imagen Final (Nginx + FastAPI)
    # ---------------------------
    FROM nginx:alpine AS final
    WORKDIR /final
    
    # Copiar el frontend construido en la imagen final
    COPY --from=frontend-builder /build-frontend/dist /usr/share/nginx/html
    
    # Copiar el backend construido (¡incluyendo el entorno virtual!) desde la etapa backend-builder
    COPY --from=backend-builder /build-backend/backend /final/backend
    
    # Asegurar que la carpeta del frontend exista (DEBUG - Puedes eliminar esta línea en producción si quieres)
    RUN ls -lah /usr/share/nginx/html || (echo "⚠️ ERROR: No se copiaron los archivos del frontend" && exit 1)
    
    # Copiar la configuración personalizada de Nginx (si tienes nginx.conf en la raíz)
    COPY nginx.conf /etc/nginx/nginx.conf
    
    # Exponer puertos: 80 para Nginx
    EXPOSE 80
    
    # Comando para ejecutar el backend (Uvicorn) en segundo plano y luego iniciar Nginx
    CMD ["sh", "-c", "/final/backend/.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000 & nginx -t && nginx -g 'daemon off;'"]