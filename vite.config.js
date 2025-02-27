import { defineConfig } from 'vite';
import preact from '@preact/preset-vite';

export default defineConfig({
  plugins: [preact()],
  base: "./", // Evita problemas de rutas en producción
  build: {
    outDir: "dist", // Asegura que el build se guarde en "dist"
  },
  server: {
    host: true,
    port: 80, // Usa el puerto de Railway o 3000 por defecto
  },
});