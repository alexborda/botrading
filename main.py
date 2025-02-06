import os
import time
import json
import openai
import requests
import hashlib
import hmac
import asyncio
import websockets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Inicializar FastAPI
app = FastAPI()

# Configuración de CORS para permitir conexiones desde el frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://bot-control-ui.onrender.com"],  # Cambia por tu frontend en producción
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración de Bybit API
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")
BYBIT_BASE_URL = "https://api-testnet.bybit.com"  # Testnet URL
BYBIT_WS_URL = "wss://stream-testnet.bybit.com/v5/public/spot"  # WebSocket Bybit para datos en vivo
BYBIT_WS_PRIVATE = "wss://stream-testnet.bybit.com/v5/private"  # WebSocket para órdenes

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "supersecreto123")  # Token para TradingView Webhook

if not BYBIT_API_KEY or not BYBIT_API_SECRET:
    raise ValueError("Faltan las claves de API de Bybit. Agrégalas en Render.")

# Configuración de OpenAI (opcional)
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
    params["timestamp"] = int(time.time() * 1000)
    sorted_params = sorted(params.items())
    query_string = "&".join([f"{key}={value}" for key, value in sorted_params])
    signature = hmac.new(BYBIT_API_SECRET.encode(), query_string.encode(), hashlib.sha256).hexdigest()
    params["sign"] = signature
    return params

@app.post("/trade")
def trade(order_type: str, symbol: str, qty: float, price: float = None, stop_loss: float = None, take_profit: float = None, trailing_stop: float = None):
    """Ejecuta una orden en Bybit con soporte para Stop-Loss, Take-Profit y Trailing Stop."""
    if order_type.lower() not in ["buy", "sell"]:
        raise HTTPException(status_code=400, detail="order_type debe ser 'buy' o 'sell'")

    order_payload = {
        "symbol": symbol,
        "side": "Buy" if order_type.lower() == "buy" else "Sell",
        "order_type": "Market" if price is None else "Limit",
        "qty": qty,
        "time_in_force": "GTC",
    }
    if price:
        order_payload["price"] = price
    if stop_loss:
        order_payload["stop_loss"] = stop_loss
    if take_profit:
        order_payload["take_profit"] = take_profit
    if trailing_stop:
        order_payload["trailing_stop"] = trailing_stop

    signed_payload = sign_request(order_payload)
    url = f"{BYBIT_BASE_URL}/v2/private/order/create"

    response = requests.post(url, json=signed_payload)
    try:
        result = response.json()
        if result.get("ret_code") != 0:
            raise HTTPException(status_code=400, detail=result.get("ret_msg", "Error en la orden"))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/webhook")
async def webhook(data: dict):
    """Recibe señales de TradingView y ejecuta órdenes en Bybit."""
    if data.get("secret") != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Acceso no autorizado")

    try:
        return trade(
            order_type=data.get("order_type", "market"),
            symbol=data.get("symbol", "BTCUSDT"),
            qty=float(data.get("qty", 0.01)),
            price=float(data.get("take_profit")) if "take_profit" in data else None,
            stop_loss=float(data.get("stop_loss")) if "stop_loss" in data else None,
            trailing_stop=float(data.get("trailing_stop")) if "trailing_stop" in data else None,
            break_even=float(data.get("break_even")) if "break_even" in data else None,
            hedging=bool(data.get("hedging", False))
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# WebSocket para recibir datos de mercado en tiempo real desde Bybit
@app.websocket("/ws/market")
async def websocket_market(websocket: WebSocket):
    await websocket.accept()
    async with websockets.connect(BYBIT_WS_URL) as ws:
        subscribe_message = {
            "op": "subscribe",
            "args": ["tickers.BTCUSDT"]
        }
        await ws.send(json.dumps(subscribe_message))

        try:
            while True:
                response = await ws.recv()
                data = json.loads(response)
                await websocket.send_json(data)
        except WebSocketDisconnect:
            print("Cliente desconectado de Market WebSocket")

# WebSocket para recibir actualizaciones de órdenes en tiempo real
@app.websocket("/ws/orders")
async def websocket_orders(websocket: WebSocket):
    await websocket.accept()
    async with websockets.connect(BYBIT_WS_PRIVATE) as ws:
        expires = int(time.time()) + 10
        signature_payload = f"GET/realtime{expires}"
        signature = hmac.new(BYBIT_API_SECRET.encode(), signature_payload.encode(), hashlib.sha256).hexdigest()

        auth_message = {
            "op": "auth",
            "args": [BYBIT_API_KEY, expires, signature]
        }
        await ws.send(json.dumps(auth_message))

        subscribe_message = {
            "op": "subscribe",
            "args": ["order"]
        }
        await ws.send(json.dumps(subscribe_message))

        try:
            while True:
                response = await ws.recv()
                data = json.loads(response)
                await websocket.send_json(data)
        except WebSocketDisconnect:
            print("Cliente desconectado de Orders WebSocket")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
