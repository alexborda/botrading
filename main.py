import os
import ssl
import uvicorn
import time
import json
import requests
import hashlib
import hmac
import asyncio
import websockets
import logging
from decimal import Decimal
from collections import OrderedDict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
logging.getLogger("uvicorn.access").setLevel(logging.CRITICAL)  # Oculta logs de acceso

# Estado del bot
bot_running = False

# Inicializar FastAPI
app = FastAPI()

# Variables de entorno
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "supersecreto123")
BYBIT_BASE_URL = os.getenv("BYBIT_BASE_URL", "https://api-testnet.bybit.com")
BYBIT_WS_URL = os.getenv("BYBIT_WS_URL", "wss://stream-testnet.bybit.com/v5/public/spot")
BYBIT_WS_PRIVATE = os.getenv("BYBIT_WS_PRIVATE", "wss://stream-testnet.bybit.com/v5/private")

# Configuración de CORS
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if not BYBIT_API_KEY or not BYBIT_API_SECRET:
    raise ValueError("Faltan las claves de API de Bybit. Agrégalas en Render.")

@app.get("/")
def root():
    return {"message": "API de Trading en Bybit 🚀"}

# Función para obtener el timestamp de Bybit
def get_timestamp():
    url = f"{BYBIT_BASE_URL}/v5/market/time"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return str(response.json()["time"])  # Devolver timestamp en formato string
    except requests.exceptions.RequestException as e:
        print(f"❌ Error obteniendo timestamp de Bybit: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener timestamp de Bybit")
    
# Función para firmar solicitudes de Bybit
def sign_request(order_payload: dict, timestamp: str) -> dict:
    """Firma la solicitud para Bybit usando HMAC SHA256."""
    recv_window = "5000"

    # Convertir el payload en JSON comprimido
    raw_request_body = json.dumps(order_payload, separators=(',', ':'))

    # Crear la cadena para la firma
    signature_string = f"{timestamp}{BYBIT_API_KEY}{recv_window}{raw_request_body}"

    # Generar la firma HMAC-SHA256
    signature = hmac.new(
        BYBIT_API_SECRET.encode(), signature_string.encode(), hashlib.sha256
    ).hexdigest()

    # Agregar la firma y timestamp al payload
    order_payload["sign"] = signature
    order_payload["timestamp"] = timestamp

    print("📡 Payload antes de firmar:", order_payload)  # Debugging
    print("🔑 Firma generada:", signature)  # Debugging

    return order_payload

@app.post("/trade")
async def trade(request: Request):
    """Ejecuta una orden en Bybit con Stop-Loss, Take-Profit y Trailing Stop."""
    try:
        data = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error procesando JSON: {str(e)}")

    # Validar que el JSON tiene los campos correctos
    required_fields = ["secret", "category", "symbol", "side", "order_type", "qty"]
    for field in required_fields:
        if field not in data:
            raise HTTPException(status_code=400, detail=f"Falta el campo requerido: {field}")

    # Validar Webhook Secret
    if data.get("secret") != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Acceso no autorizado")
    
    timestamp = str(int(time.time() * 1000))
    recv_window = "5000"

    # Obtener datos de la orden
    category = data.get("category", "linear").lower()  # Tipo de mercado (linear, inverse, spot, option)
    symbol = data.get("symbol", "BTCUSDT").strip().upper()
    side = data.get("side", "Buy").capitalize()  # Asegura que sea "Buy" o "Sell"
    order_type = data.get("order_type", "limit").lower()  # market, limit, stop_limit, stop_market
    qty = str(Decimal(str(data.get("qty", 0.01))))  # Mantiene precisión decimal

    # Construcción del payload de orden para Bybit
    order_payload = {
        "category": category,
        "symbol": symbol,
        "side": side,
        "orderType": order_type,
        "qty": qty,
        "timeInForce": "GTC",
    }
    # Validar si es orden `Limit` y agregar `price`
    if order_payload["orderType"] == "limit" and data.get("price") is not None:
        order_payload["price"] = str(data["price"])

    # Agregar parámetros opcionales (stopLoss, takeProfit, trailingStop)
    if data.get("stop_loss") is not None:
        order_payload["stopLoss"] = str(data["stop_loss"])
    if data.get("take_profit") is not None:
        order_payload["takeProfit"] = str(data["take_profit"])
    if data.get("trailing_stop") is not None:
        order_payload["trailingStop"] = str(data["trailing_stop"])

    # Validar cantidad
    if Decimal(qty) <= 0:
        raise HTTPException(status_code=400, detail="Cantidad debe ser mayor a 0")

    # Firmar la solicitud
    signed_payload, timestamp = sign_request(order_payload)

    # **Headers con autenticación**
    headers = {
        "X-BAPI-SIGN": signed_payload["sign"],
        "X-BAPI-API-KEY": BYBIT_API_KEY,
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-RECV-WINDOW": recv_window,
        "Content-Type": "application/json"
    }

    # **Enviar solicitud a Bybit con reintento**
    url = f"{BYBIT_BASE_URL}/v5/order/create"
    for attempt in range(3):  # Intentar hasta 3 veces si falla
        response = requests.post(url, headers=headers, json=order_payload)
        
        print(f"🔍 Intento {attempt + 1} - Status Code: {response.status_code}")
        print(f"🔍 Headers: {response.headers}")
        print(f"🔍 Raw Response: {response.text}")

        if response.status_code == 500:
            print("⚠️ Error 500, reintentando en 2 segundos...")
            time.sleep(2)
            continue  # Reintentar
        break  # Salir del bucle si no es error 500

    # Verificar si la respuesta es válida
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=f"Bybit Error: {response.text}")

    try:
        result = response.json()
        print("📡 Respuesta JSON de Bybit:", json.dumps(result, indent=2))

        if result.get("retCode") != 0:
            print(f"❌ Error de Bybit: {result.get('retMsg')}")
            raise HTTPException(status_code=400, detail=result.get("retMsg", "Error en la orden"))

        return {"status": "success", "data": result}
    except requests.exceptions.JSONDecodeError:
        print("❌ Error: La respuesta de Bybit no es JSON o está vacía.")
        raise HTTPException(status_code=500, detail=f"Bybit devolvió una respuesta inválida: {response.text}")
    
@app.get("/status")
def get_status():
    """Devuelve el estado actual del bot"""
    return {"status": bot_running}

@app.post("/start")
async def start_bot():
    global bot_running  # Añadir global para modificar la variable
    try:
        # Código para iniciar el bot
        bot_running = True  #Asegurar que cambia a True
        print("✅ Bot iniciado correctamente")
        return {"status": bot_running}  #Devuelve el nuevo estado
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/stop")
async def stop_bot():
    global bot_running  # ⚡ Añadir global para modificar la variable
    try:
        # Código para detener el bot
        bot_running = False  #Asegurar que cambia a False
        print("✅ Bot detenido correctamente")
        return {"status": bot_running}  #Devuelve el nuevo estado
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.websocket("/ws/market")
async def websocket_market(websocket: WebSocket):
    await websocket.accept()
    try:
        async with websockets.connect(BYBIT_WS_URL) as ws:
            # Suscribirse a tickers de mercado
            subscribe_message = {"op": "subscribe", "args": ["tickers.ETHUSDT"]}
            await ws.send(json.dumps(subscribe_message))

            while True:
                response = await ws.recv()
                data = json.loads(response)
                print("📡 Enviando datos de mercado al frontend:", data)  # <-- Log para debug
                await websocket.send_json(data)  # <-- Enviar datos al frontend
                await asyncio.sleep(1)  # Reducir carga
    except Exception as e:
        print(f"Error en WebSocket Market: {e}")

@app.websocket("/ws/orders")
async def websocket_orders(websocket: WebSocket):
    await websocket.accept()
    try:
        ssl_context = ssl.create_default_context()
        async with websockets.connect(BYBIT_WS_PRIVATE) as ws:
            expires = int(time.time()) + 10
            signature_payload = f"GET/realtime{expires}"
            signature = hmac.new(
                BYBIT_API_SECRET.encode(), 
                signature_payload.encode(), 
                "sha256"
            ).hexdigest()

            auth_message = {"op": "auth", "args": [BYBIT_API_KEY, expires, signature]}
            await ws.send(json.dumps(auth_message))

            subscribe_message = {"op": "subscribe", "args": ["order"]}
            await ws.send(json.dumps(subscribe_message))

            while True:
                try:
                    response = await ws.recv()
                    data = json.loads(response)
                    await websocket.send_json(data)
                    await asyncio.sleep(5)  # Evita desconexiones
                except websockets.exceptions.ConnectionClosed:
                    print("Conexión WebSocket de Orders cerrada, reconectando...")
                    await asyncio.sleep(2)
                    continue
    except Exception as e:
        print(f"Error en Orders WebSocket: {e}")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))  # Railway asigna dinámicamente el puerto
    uvicorn.run(app, host="0.0.0.0", port=port)