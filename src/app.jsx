import { useState, useEffect, useCallback} from "preact/hooks";

const API_URL = "https://botrading.fly.dev";
const API_WS_URL = "wss://botrading.fly.dev";
const WS_URL_MARKET = API_WS_URL + "/ws/market"; //Asegurar wss://
const WS_URL_ORDERS = API_WS_URL + "/ws/orders"; //Asegurar wss://

export function App() {
  const [status, setStatus] = useState(null);
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [qty, setQty] = useState(0.01);
  const [orderType, setOrderType] = useState("buy");
  const [price, setPrice] = useState(null);
  const [orders, setOrders] = useState([]);
  const [activeTab, setActiveTab] = useState("status");
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  const [menuOpen, setMenuOpen] = useState(false);
  const [darkMode, setDarkMode] = useState(() => {
    const savedTheme = localStorage.getItem("theme");
    return savedTheme ? savedTheme === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
  });

  // WebSocket con reconexión automática (con límite de intentos)
  const setupWebSocket = (url, onMessage, retries = 5) => {
    if (retries <= 0) return;
  
    let ws = new WebSocket(url);
  
    ws.onopen = () => {
      console.log(`✅ Conectado a WebSocket: ${url}`);
      
      //Suscribirse al canal de precios de BTC/USDT en Bybit
      const subscribeMessage = { op: "subscribe", args: ["tickers.BTCUSDT"] };
      ws.send(JSON.stringify(subscribeMessage)); //Enviar la suscripción aquí
    };
  
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      console.log("📡 Mensaje recibido del WebSocket:", data);
      
      if (data?.success === false) {
        console.error("⚠️ Error en suscripción:", data);
        return;
      }
  
      if (data.topic === "tickers.BTCUSDT" && data.data) {
        console.log("📊 Precio actualizado:", data.data.lastPrice);
        onMessage(data);
      }
    };
  
    ws.onerror = (error) => console.error(`❌ Error en WebSocket ${url}:`, error);
  
    ws.onclose = () => {
      console.warn(`⚠️ WebSocket cerrado. Reintentando conexión (${retries - 1} intentos restantes)...`);
      setTimeout(() => setupWebSocket(url, onMessage, retries - 1), 3000);
    };
  
    return ws;
  };
  
  // Conectar al WebSocket de Market con `wss://`
useEffect(() => {
  let ws;

  const connectWebSocket = () => {
    ws = new WebSocket(WS_URL_MARKET);

    ws.onopen = () => {
      console.log("✅ Conectado a WebSocket de mercado.");
      ws.send(JSON.stringify({ op: "subscribe", args: ["tickers.BTCUSDT"] }));
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.topic === "tickers.BTCUSDT" && message.data) {
          const lastPrice = message.data.lastPrice;
          console.log("📡 Precio actualizado:", lastPrice);
          setPrice(lastPrice);
        }
      } catch (error) {
        console.error("⚠️ Error procesando mensaje WebSocket:", error);
      }
    };

    ws.onerror = (error) => console.error("⚠️ Error en WebSocket de mercado:", error);

    ws.onclose = () => {
      console.warn("⚠️ WebSocket cerrado. Intentando reconectar en 3s...");
      setTimeout(connectWebSocket, 3000); // Reintenta sin recargar la página
    };
  };

  connectWebSocket(); //Iniciar conexión

  return () => {
    console.log("🛑 Cerrando WebSocket de mercado...");
    ws?.close();
  };
}, []);


// Conectar al WebSocket de Orders con `wss://`
useEffect(() => {
  console.log("🌐 Conectando a WebSocket de órdenes:", WS_URL_ORDERS);
  const ws = setupWebSocket(WS_URL_ORDERS, (data) => setOrders((prevOrders) => [...prevOrders, data]));
  return () => ws?.close();
}, []);

  //Enviar orden
  const sendOrder = async () => {
    const order = {
      secret: import.meta.env.VITE_API_SECRET,
      order_type: orderType,
      symbol,
      qty,
      price,
    };
    try {
      const response = await fetch(`${API_URL}/trade`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(order),
      });
      const result = await response.json();
      setOrders((prevOrders) => [...prevOrders, result]);
    } catch (error) {
      console.error("⚠️ Error al enviar la orden:", error);
    }
  };

//Obtener estado del bot
const fetchStatus = async () => {
  try {
    const res = await fetch(`${API_URL}/status?t=${Date.now()}`); //Evita caché con un timestamp
    if (!res.ok) throw new Error("Error al obtener el estado");
    const data = await res.json();
    setStatus(data.status);
  } catch (error) {
    console.error("⚠️ Error al obtener estado:", error);
    setStatus(null);
  }finally {
    isFetching = false;
  }
};

useEffect(() => {
  const fetchWhenVisible = () => {
    if (document.visibilityState === "visible") {
      fetchStatus();
    }
  };

  document.addEventListener("visibilitychange", fetchWhenVisible);
  const interval = setInterval(fetchStatus, 30000);

  return () => {
    clearInterval(interval);
    document.removeEventListener("visibilitychange", fetchWhenVisible);
  };
}, []);

// Manejar inicio del bot
const handleStart = async () => {
  try {
    const res = await fetch(`${API_URL}/start`, { method: "POST" });
    if (!res.ok) throw new Error("Error al iniciar el bot");
    const data = await res.json();
    console.log("✅ Bot iniciado:", data);

    await fetchStatus(); //Forzar actualización inmediata
  } catch (error) {
    console.error("⚠️ Error al iniciar el bot:", error);
  }
};

// Manejar detención del bot
const handleStop = async () => {
  try {
    const res = await fetch(`${API_URL}/stop`, { method: "POST" });
    if (!res.ok) throw new Error("Error al detener el bot");
    const data = await res.json();
    console.log("🛑 Bot detenido:", data);

    await fetchStatus(); //Forzar actualización inmediata
  } catch (error) {
    console.error("⚠️ Error al detener el bot:", error);
  }
};

  // Detectar si es móvil
  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth < 768);
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  //Modo oscuro
  useEffect(() => {
    const root = document.documentElement;
    if (darkMode) {
      root.classList.add("dark");
      localStorage.setItem("theme", "dark");
    } else {
      root.classList.remove("dark");
      localStorage.setItem("theme", "light");
    }
  }, [darkMode]);

  return (
    <div className={`app ${darkMode ? "dark" : ""}`}>
      <header className="header">
        <nav className="navbar">
          <h1 className="navbar-title">Trading Bot {isMobile ? "📱" : "💻"}</h1>
          <div className="hidden md:flex space-x-4">
            <button className="menu-item" onClick={() => setMenuOpen(!menuOpen)}>☰</button>
            <button className="menu-item" onClick={() => setActiveTab("status")}>📊 Estado</button>
            <button className="menu-item" onClick={() => setActiveTab("order")}>🛒 Ordenes</button>
            <button className="menu-item" onClick={() => setActiveTab("price")}>💰 Precios</button>
            <button className="menu-item" onClick={() => setDarkMode(!darkMode)}>
              {darkMode ? "🌞 Light" : "🌙 Dark"}
            </button>
          </div>
        </nav>
      </header>

      {/* MENÚ DESPLEGABLE */}
      {menuOpen && (
        <div className="submenu">
          <button onClick={handleStart} disabled={status} className="button">🟢 Start</button>
          <button onClick={handleStop} disabled={!status} className="button">🔴 Stop</button>
        </div>
      )}

      {/* Contenido dinámico */}
      <div className="container">
        {activeTab === "status" && (
          <div className="card">
            <h2>📊 Estado del Bot</h2>
            <p>{status === null ? "Cargando..." : status ? "🟢 Activo" : "🔴 Inactivo"}</p>
          </div>
        )}
        {activeTab === "order" && (
          <div className="card">
            <h2>🛒 Enviar Orden</h2>
            <form onSubmit={(e) => { e.preventDefault(); sendOrder(); }}>
              <label>Símbolo:</label>
              <input type="text" value={symbol} onChange={(e) => setSymbol(e.target.value)} className="input-field" />
              <label>Cantidad:</label>
              <input type="number" value={qty} onChange={(e) => setQty(Number(e.target.value))} className="input-field" />
              <label>Tipo de Orden:</label>
              <select value={orderType} onChange={(e) => setOrderType(e.target.value)} className="input-field">
                <option value="buy">Comprar</option>
                <option value="sell">Vender</option>
              </select>
              <button type="submit" className="button">📩 Enviar Orden</button>
            </form>
          </div>
        )}
        {activeTab === "price" && (
          <div className="card">
            <h2>💰 Precios en Vivo</h2>
            <p>{price !== null ? `$${price}` : "Cargando..."}</p>
          </div>
        )}

      </div>

      <footer className="footer">Creado con ❤️ para optimizar el trading 📈</footer>
    </div>
  );
}
