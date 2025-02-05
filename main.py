import os
import pandas as pd
import time
import json
import openai
import requests
import hashlib
import hmac
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://bot-control-ui.onrender.com"],  # SOLO tu frontend en producción
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración de la API de Bybit
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")
BYBIT_BASE_URL = "https://api-testnet.bybit.com"  # URL para Testnet
BYBIT_WS_URL = "wss://stream-testnet.bybit.com/v5/public/spot"  # WebSocket para datos en vivo

if not BYBIT_API_KEY or not BYBIT_API_SECRET:
    raise ValueError("Faltan las claves de API de Bybit. Agrégalas en Render.")

# Configuración de OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("Falta la API Key de OpenAI. Agrégala en Render.")
openai.api_key = OPENAI_API_KEY

app = FastAPI()

@app.get("/")
def root():
    return {"message": "API de Trading con OpenAI y Bybit 🚀"}

@app.post("/ask_chatgpt")
def ask_chatgpt(prompt: str):
    """
    Envía una consulta a ChatGPT sobre predicciones, estrategias y análisis de trading.
    """
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "system", "content": "Eres un asistente experto en trading y análisis financiero."},
                      {"role": "user", "content": prompt}]
        )
        return {"response": response["choices"][0]["message"]["content"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/trade")
def trade(order_type: str, symbol: str, qty: float, price: float):
    """Ejecuta una orden en Bybit."""
    url = f"{BYBIT_BASE_URL}/v2/private/order/create"
    headers = {
        "Content-Type": "application/json"
    }
    payload = {
        "api_key": BYBIT_API_KEY,
        "symbol": symbol,
        "side": "Buy" if order_type == "buy" else "Sell",
        "order_type": "Limit",
        "qty": qty,
        "price": price,
        "time_in_force": "GTC"
    }
    response = requests.post(url, json=payload, headers=headers)
    return response.json()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
