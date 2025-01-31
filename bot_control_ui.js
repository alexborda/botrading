const startBot = async () => {
    try {
      const response = await fetch("https://tu-bot.onrender.com/start", {
        method: "POST",
      });
      const data = await response.json();
      setBotStatus("running");
    } catch (error) {
      console.error("Error al iniciar el bot", error);
    }
  };
  
  const stopBot = async () => {
    try {
      const response = await fetch("https://tu-bot.onrender.com/stop", {
        method: "POST",
      });
      const data = await response.json();
      setBotStatus("stopped");
    } catch (error) {
      console.error("Error al detener el bot", error);
    }
  };
  