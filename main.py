import os
import numpy as np
import joblib
import tensorflow as tf
from fastapi import FastAPI, HTTPException
from tensorflow.keras.models import load_model
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from sklearn.preprocessing import MinMaxScaler
import pandas as pd
import requests

# Configuración de la API de Bybit
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")
BYBIT_BASE_URL = "https://api.bybit.com"

# Cargar modelo y scaler si existen
MODEL_PATH = "lstm_model.h5"
SCALER_PATH = "scaler.pkl"

app = FastAPI()

# Verificar si el modelo existe, si no, entrenarlo
def train_and_save_model():
    data = pd.read_csv("historical_data.csv")
    scaler = MinMaxScaler()
    data["close_scaled"] = scaler.fit_transform(data["close"].values.reshape(-1, 1))

    seq_length = 50
    X, y = [], []
    for i in range(len(data) - seq_length):
        X.append(data["close_scaled"].iloc[i:i+seq_length].values)
        y.append(data["close_scaled"].iloc[i+seq_length])
    
    X, y = np.array(X), np.array(y)

    model = Sequential([
        LSTM(64, return_sequences=True, input_shape=(X.shape[1], X.shape[2])),
        Dropout(0.2),
        LSTM(32, return_sequences=False),
        Dense(25, activation="relu"),
        Dense(1)
    ])

    model.compile(optimizer="adam", loss="mse")
    model.fit(X, y, epochs=50, batch_size=32)
    
    model.save(MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)

# Entrenar modelo si no existe
if not os.path.exists(MODEL_PATH) or not os.path.exists(SCALER_PATH):
    train_and_save_model()

# Cargar modelo y scaler
model = load_model(MODEL_PATH)
scaler = joblib.load(SCALER_PATH)

@app.get("/")
def root():
    return {"message": "API de Trading con Deep Learning 🚀"}

@app.post("/predict")
def predict(data: list):
    if len(data) != 50:
        raise HTTPException(status_code=400, detail="Debes enviar exactamente 50 valores de precio.")
    
    input_data = np.array(data).reshape(1, 50, 1)
    prediction = model.predict(input_data)
    predicted_price = scaler.inverse_transform(prediction.reshape(-1,1))[0][0]
    
    return {"predicted_price": predicted_price}

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