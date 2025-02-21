import os
import ssl
import uvicorn
import time
import json
import openai
import requests
import hashlib
import hmac
import asyncio
import websockets
from decimal import Decimal
from collections import OrderedDict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

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

# Configuración de OpenAI (Opcional)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("Falta la API Key de OpenAI. Agrégala en Render.")
openai.api_key = OPENAI_API_KEY

@app.get("/")
def root():
    return {"message": "API de Trading con OpenAI y Bybit 🚀"}

# Función para firmar solicitudes de Bybit
def sign_request(params: dict) -> dict:
    """Firma la solicitud para Bybit usando HMAC SHA256."""
    params["api_key"] = BYBIT_API_KEY
    params["timestamp"] = str(int(time.time() * 1000))

    # Crear firma ordenada
    sorted_params = OrderedDict(sorted(params.items()))
    query_string = "&".join([f"{key}={value}" for key, value in sorted_params.items()])

    signature = hmac.new(
        BYBIT_API_SECRET.encode(), query_string.encode(), hashlib.sha256
    ).hexdigest()

    params["sign"] = signature
    print("📡 Payload antes de firmar:", params)  # Imprimir los parámetros firmados
    print("🔑 Firma generada:", signature)  # Imprimir la firma
    return params

@app.get("/status")
def get_status():
    """Devuelve el estado actual del bot"""
    return {"status": bot_running}

@app.post("/start")
async def start_bot():
    global bot_running  # ⚡ Añadir global para modificar la variable
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

@app.post("/trade")
async def trade(request: Request):
    """Ejecuta una orden en Bybit con Stop-Loss, Take-Profit y Trailing Stop."""
    try:
        data = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error procesando JSON: {str(e)}")
    
    # Validar que el JSON tiene los campos correctos
    required_fields = ["secret", "symbol", "side", "order_type", "qty"]
    for field in required_fields:
        if field not in data:
            raise HTTPException(status_code=400, detail=f"Falta el campo requerido: {field}")

    return {"message": "Solicitud procesada correctamente", "data": data}

    # Validar Webhook Secret
    if data.get("secret") != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Acceso no autorizado")

    # Obtener datos de la orden
    symbol = data.get("symbol", "BTCUSDT").strip().upper()
    side = data.get("side", "Buy").capitalize()  # Asegura que sea "Buy" o "Sell"
    order_type = data.get("order_type", "market").lower()  # market, limit, stop_limit, stop_market
    qty = str(Decimal(str(data.get("qty", 0.01))))  # Mantiene precisión decimal
    
    # Validar cantidad
    if Decimal(qty) <= 0:
        raise HTTPException(status_code=400, detail="Cantidad debe ser mayor a 0")

    # Construcción del payload de orden
    order_payload = {
        "symbol": symbol,
        "side": side,  # "Buy" o "Sell"
        "order_type": order_type.capitalize(),  # "Market" o "Limit"
        "qty": qty,
        "time_in_force": "GoodTillCancel",  # Mantener la orden hasta que se ejecute o cancele
    }

    # Validar si es orden `Limit` y agregar `price`
    if order_type == "limit" and data.get("price") is not None:
        order_payload["price"] = str(data["price"])

    # Opcionales
    if data.get("stop_loss") is not None:
        order_payload["stop_loss"] = str(data["stop_loss"])
    if data.get("take_profit") is not None:
        order_payload["take_profit"] = str(data["take_profit"])
    if data.get("trailing_stop") is not None:
        order_payload["trailing_stop"] = str(data["trailing_stop"])
    # Firmar la solicitud
    signed_payload = sign_request(order_payload)

    # Enviar solicitud a Bybit
    url = f"{BYBIT_BASE_URL}/private/linear/order/create"
    response = requests.post(url, json=signed_payload)
    print("📡 Respuesta de Bybit:", response.json())  #Ver qué responde Bybit
    try:
        result = response.json()
        if result.get("ret_code") != 0:
            raise HTTPException(status_code=400, detail=result.get("ret_msg", "Error en la orden"))
        return {"status": "success", "data": result}
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