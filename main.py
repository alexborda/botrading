from fastapi import FastAPI
import requests

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "API de Trading en Bybit Activa 🚀"}

@app.get("/price/{symbol}")
def get_price(symbol: str):
    url = f"https://api.bybit.com/v2/public/tickers?symbol={symbol}"
    response = requests.get(url)
    return response.json()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

