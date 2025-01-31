from fastapi import FastAPI, WebSocket, Depends, HTTPException, Header
import uvicorn
import requests
import asyncio

# Configuración de la API
app = FastAPI()
BYBIT_API_KEY = "TU_API_KEY"
BYBIT_API_SECRET = "TU_API_SECRET"

# Función para validar API Key personalizada
def validate_api_key(x_api_key: str = Header(...)):
    if x_api_key != "TU_CLAVE_SECRETA":
        raise HTTPException(status_code=401, detail="Acceso no autorizado")
    return x_api_key

# Ruta de prueba
@app.get("/")
def root():
    return {"message": "API de Trading en Bybit Activa 🚀"}

# Conectar con Bybit y enviar órdenes
@app.post("/trade")
def trade(order_type: str, symbol: str, qty: float, price: float, api_key: str = Depends(validate_api_key)):
    url = "https://api.bybit.com/v2/private/order/create"
    payload = {
        "api_key": BYBIT_API_KEY,
        "symbol": symbol,
        "side": "Buy" if order_type == "buy" else "Sell",
        "order_type": "Limit",
        "qty": qty,
        "price": price,
        "time_in_force": "GTC"
    }
    response = requests.post(url, json=payload)
    return response.json()

# WebSocket para recibir precios en tiempo real
@app.websocket("/ws/{symbol}")
async def websocket_endpoint(websocket: WebSocket, symbol: str):
    await websocket.accept()
    while True:
        price = obtener_precio(symbol)  # Implementa esta función con la API de Bybit
        await websocket.send_json({"symbol": symbol, "price": price})
        await asyncio.sleep(1)  # Cada 1 segundo

# Función para obtener precio desde Bybit
def obtener_precio(symbol: str):
    url = f"https://api.bybit.com/v2/public/tickers?symbol={symbol}"
    response = requests.get(url).json()
    return response['result'][0]['last_price'] if 'result' in response else None

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)