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
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "").split(",")# Configuración de CORS

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
def sign_request(payload: dict) -> dict:
    """Firma la solicitud para Bybit usando HMAC SHA256."""
    payload["api_key"] = BYBIT_API_KEY
    payload["timestamp"] = int(time.time() * 1000)

    # Asegurar orden de parámetros para la firma
    sorted_payload = OrderedDict(sorted(payload.items()))
    payload_json = json.dumps(sorted_payload, separators=(',', ':'))
    
    signature = hmac.new(BYBIT_API_SECRET.encode(), payload_json.encode(), hashlib.sha256).hexdigest()
    payload["sign"] = signature
    return payload

@app.get("/status")
def get_status():
    """Devuelve el estado actual del bot"""
    return {"status": bot_running}

@app.post("/start")
async def start_bot():
    global bot_running  # ⚡ Añadir global para modificar la variable
    try:
        # Código para iniciar el bot
        bot_running = True  # ✅ Asegurar que cambia a True
        print("✅ Bot iniciado correctamente")
        return {"status": bot_running}  # ✅ Devuelve el nuevo estado
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/stop")
async def stop_bot():
    global bot_running  # ⚡ Añadir global para modificar la variable
    try:
        # Código para detener el bot
        bot_running = False  # ✅ Asegurar que cambia a False
        print("✅ Bot detenido correctamente")
        return {"status": bot_running}  # ✅ Devuelve el nuevo estado
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/trade")
async def trade(request: Request):
    """Ejecuta una orden en Bybit con Stop-Loss, Take-Profit y Trailing Stop."""
    data = await request.json()

    if data.get("secret") != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Acceso no autorizado")

    order_type = data.get("order_type", "market").lower()
    symbol = data.get("symbol", "BTCUSDT").strip().upper()
    
    try:
        qty = Decimal(str(data.get("qty", 0.01)))  # Precisión con Decimal
        if qty <= 0:
            raise ValueError("Cantidad debe ser mayor a 0")
    except:
        raise HTTPException(status_code=400, detail="Cantidad inválida")

    if order_type not in ["buy", "sell"]:
        raise HTTPException(status_code=400, detail="order_type debe ser 'buy' o 'sell'")

    order_payload = {
        "symbol": symbol,
        "side": "Buy" if order_type == "buy" else "Sell",
        "order_type": "Market" if data.get("price") is None else "Limit",
        "qty": str(qty),
        "time_in_force": "GTC",
        "price": data.get("price"),
        "stop_loss": data.get("stop_loss"),
        "take_profit": data.get("take_profit"),
        "trailing_stop": data.get("trailing_stop"),
    }

    order_payload = {k: v for k, v in order_payload.items() if v is not None}
    signed_payload = sign_request(order_payload)

    url = f"{BYBIT_BASE_URL}/v2/private/order/create"
    response = requests.post(url, json=signed_payload)

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
            subscribe_message = {"op": "subscribe", "args": ["tickers.BTCUSDT"]}
            await ws.send(json.dumps(subscribe_message))

            while True:
                response = await ws.recv()
                data = json.loads(response)
                print("📡 Enviando datos al frontend:", data)  # <-- Agregar este log
                await websocket.send_json(data)  # <-- Asegurar que enviamos datos
                await asyncio.sleep(1)
    except Exception as e:
        print(f"❌ Error en WebSocket Market: {e}")

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
        print(f"❌ Error en Orders WebSocket: {e}")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))  # Railway asigna dinámicamente el puerto
    uvicorn.run(app, host="0.0.0.0", port=port)