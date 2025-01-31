import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export default function BotControl() {
  const [botStatus, setBotStatus] = useState("stopped");
  const [log, setLog] = useState([]);

  useEffect(() => {
    // Verificar el estado inicial del bot desde Render
    const fetchStatus = async () => {
      try {
        const response = await fetch("https://trading-bot-kv25.onrender.com/status");
        const data = await response.json();
        setBotStatus(data.bot_running ? "running" : "stopped");
      } catch (error) {
        console.error("Error obteniendo el estado del bot", error);
      }
    };
    fetchStatus();
  }, []);

  const startBot = async () => {
    try {
      const response = await fetch("https://trading-bot-kv25.onrender.com/start", {
        method: "POST",
      });
      const data = await response.json();
      setBotStatus("running");
      setLog((prev) => [...prev, "Bot iniciado"]);
    } catch (error) {
      console.error("Error al iniciar el bot", error);
      setLog((prev) => [...prev, "Error al iniciar el bot"]);
    }
  };

  const stopBot = async () => {
    try {
      const response = await fetch("https://trading-bot-kv25.onrender.com/stop", {
        method: "POST",
      });
      const data = await response.json();
      setBotStatus("stopped");
      setLog((prev) => [...prev, "Bot detenido"]);
    } catch (error) {
      console.error("Error al detener el bot", error);
      setLog((prev) => [...prev, "Error al detener el bot"]);
    }
  };

  return (
    <div className="flex flex-col items-center p-6">
      <Card className="w-96 text-center">
        <CardContent className="p-4">
          <h2 className="text-xl font-bold mb-4">Control del Bot</h2>
          <p className="mb-4">Estado del bot: <strong>{botStatus}</strong></p>
          <div className="flex space-x-4">
            <Button onClick={startBot} disabled={botStatus === "running"}>
              Iniciar Bot
            </Button>
            <Button onClick={stopBot} disabled={botStatus === "stopped"}>
              Detener Bot
            </Button>
          </div>
          <div className="mt-4 text-left w-full bg-gray-100 p-2 rounded">
            <h3 className="text-md font-semibold">Registro de eventos:</h3>
            <ul className="text-sm">
              {log.map((entry, index) => (
                <li key={index}>{entry}</li>
              ))}
            </ul>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}