import os
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

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Para desarrollo
        "https://bot-control-ui.onrender.com",  # Frontend en Render
        "https://trading-bot-kv25.onrender.com",  # Backend en Render
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración de Bybit API
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")
BYBIT_BASE_URL = "https://api-testnet.bybit.com"
BYBIT_WS_URL = "wss://stream-testnet.bybit.com/v5/public/spot"
BYBIT_WS_PRIVATE = "wss://stream-testnet.bybit.com/v5/private"

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "supersecreto123")

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
    try:
        # Código para iniciar el bot
        return {"status": "Bot iniciado"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/stop")
async def stop_bot():
    try:
        # Código para detener el bot
        return {"status": "Bot detenido"}
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
                try:
                    response = await ws.recv()
                    data = json.loads(response)
                    await websocket.send_json(data)
                except websockets.exceptions.ConnectionClosed:
                    print("Conexión WebSocket de Market cerrada, reconectando...")
                    await asyncio.sleep(2)
                    continue
    except Exception as e:
        print(f"❌ Error en Market WebSocket: {e}")

@app.websocket("/ws/orders")
async def websocket_orders(websocket: WebSocket):
    await websocket.accept()
    try:
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
                except websockets.exceptions.ConnectionClosed:
                    print("Conexión WebSocket de Orders cerrada, reconectando...")
                    await asyncio.sleep(2)
                    continue
    except Exception as e:
        print(f"❌ Error en Orders WebSocket: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
