import os
import time
import json
import openai
import requests
import hashlib
import hmac
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Configuración de CORS para permitir conexiones desde el frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://bot-control-ui.onrender.com"],  # Cambia por tu frontend en producción
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración de la API de Bybit
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")
BYBIT_BASE_URL = "https://api-testnet.bybit.com"  # URL para Testnet

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "supersecreto123")  # Token de seguridad para TradingView

if not BYBIT_API_KEY or not BYBIT_API_SECRET:
    raise ValueError("Faltan las claves de API de Bybit. Agrégalas en Render.")

def sign_request(params: dict) -> dict:
    """Firma la solicitud para Bybit usando HMAC SHA256."""
    params["api_key"] = BYBIT_API_KEY
    params["timestamp"] = int(time.time() * 1000)
    sorted_params = sorted(params.items())
    query_string = "&".join([f"{key}={value}" for key, value in sorted_params])
    signature = hmac.new(BYBIT_API_SECRET.encode(), query_string.encode(), hashlib.sha256).hexdigest()
    params["sign"] = signature
    return params

@app.post("/webhook")
async def webhook(data: dict):
    """Recibe señales de TradingView y ejecuta órdenes en Bybit con SL, TP y Trailing Stop."""
    if data.get("secret") != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Acceso no autorizado")

    try:
        order_type = data.get("order_type", "market").lower()  # "market" o "limit"
        side = data.get("side", "").lower()  # "buy" o "sell"
        symbol = data.get("symbol", "BTCUSDT").upper()  # Activo
        qty = float(data.get("qty", 0.01))  # Cantidad de contrato
        price = float(data.get("price", 0)) if order_type == "limit" else None
        stop_loss = float(data.get("stop_loss", 0)) if data.get("stop_loss") else None
        take_profit = float(data.get("take_profit", 0)) if data.get("take_profit") else None
        trailing_stop = float(data.get("trailing_stop", 0)) if data.get("trailing_stop") else None

        if side not in ["buy", "sell"]:
            raise HTTPException(status_code=400, detail="El parámetro 'side' debe ser 'buy' o 'sell'")

        order_payload = {
            "symbol": symbol,
            "side": "Buy" if side == "buy" else "Sell",
            "order_type": "Market" if order_type == "market" else "Limit",
            "qty": qty,
            "time_in_force": "GTC",
        }
        if price:
            order_payload["price"] = price  # Solo para órdenes Limit
        if stop_loss:
            order_payload["stop_loss"] = stop_loss
        if take_profit:
            order_payload["take_profit"] = take_profit
        if trailing_stop:
            order_payload["trailing_stop"] = trailing_stop

        signed_payload = sign_request(order_payload)
        url = f"{BYBIT_BASE_URL}/v2/private/order/create"

        response = requests.post(url, json=signed_payload)
        result = response.json()

        if result.get("ret_code") != 0:
            raise HTTPException(status_code=400, detail=result.get("ret_msg", "Error en la orden"))

        return {"message": "Orden ejecutada correctamente", "data": result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
