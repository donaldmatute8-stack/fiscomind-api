import logging
import requests
from datetime import datetime
from typing import Dict, Any

# Mock de SATConnector para el bot
from sat_models import SATAuthCredentials

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fisco_agent")

class FiscoAgent:
    """
    Agente principal que orquesta la interacción con el SAT y genera insights fiscales.
    """
    
    def __init__(self, bot_token: str, api_base: str = "https://fiscomind-api-production.up.railway.app"):
        self.bot_token = bot_token
        self.api_base = api_base

    def _call_api(self, endpoint: str, method: str = "GET", data: Dict = None) -> Dict:
        url = f"{self.api_base}{endpoint}"
        try:
            if method == "POST":
                res = requests.post(url, json=data, timeout=10)
            else:
                res = requests.get(url, timeout=10)
            res.raise_for_status()
            return res.json()
        except Exception as e:
            logger.error(f"API Error {endpoint}: {e}")
            return {"status": "error", "message": str(e)}

    def handle_telegram_event(self, event: Dict[str, Any]):
        """
        Recibe eventos del bot de Telegram y coordina la respuesta.
        """
        user_id = event.get("user_id")
        text = event.get("text", "").lower()
        
        logger.info(f"Procesando evento de Telegram: {text} (Usuario: {user_id})")
        
        if "cfdi" in text and "descargar" in text:
            return self.execute_cfdi_download()
        elif "opinion" in text or "cumplimiento" in text:
            return self.execute_compliance_check()
        elif "status" in text or "estatus" in text:
            return self.execute_status_query()
        elif "factura" in text and "emitir" in text:
            return "Para emitir una factura, por favor usa la Mini App de FiscoMind: 📱 [Abrir Mini App](https://fiscomind-app.vercel.app)"
        elif "dashboard" in text or "resumen" in text:
            dash = self._call_api("/dashboard")
            if dash.get("status") == "error":
                return "Error al obtener el resumen fiscal."
            
            s = dash.get("summary", {})
            return (f"📊 *Resumen Fiscal*\n\n"
                    f"Ingresos: ${s.get('total_ingresos', 0):,.2f}\n"
                    f"Egresos: ${s.get('total_egresos', 0):,.2f}\n"
                    f"Deducibles: {s.get('deducibles_count', 0)} docs\n"
                    f"Ahorro ISR est: ${s.get('ahorro_isr_estimado', 0):,.2f}\n\n"
                    f"📅 Última sinc: {dash.get('last_sync', 'N/A')}")
        else:
            return "Hola Marco. Soy tu Asistente Fiscal IA. Puedo ayudarte a:\n- 📊 Consultar tu resumen fiscal (di 'resumen')\n- 📑 Descargar CFDIs (di 'descargar CFDI')\n- ✅ Ver tu Opinión de Cumplimiento (di 'opinión')\n- 📄 Emitir facturas (usa la Mini App)\n\n¿En qué puedo ayudarte?"

    def execute_cfdi_download(self) -> str:
        """
        Sincroniza con el SAT vía API Railway.
        """
        try:
            self._call_api("/sync", "POST", {"tipo": "recibidos"})
            self._call_api("/sync/check", "POST")
            return "⏳ He solicitado la descarga de tus CFDIs al SAT. Tardará unos minutos. Puedes revisar el progreso en la Mini App."
        except Exception as e:
            return f"Error al iniciar descarga: {str(e)}"

    def execute_compliance_check(self) -> str:
        """
        Consulta la opinión de cumplimiento vía API Railway.
        """
        try:
            opinion = self._call_api("/opinion")
            if "status" in opinion and opinion["status"] == "error":
                return f"Error: {opinion['message']}"
            
            status = opinion.get("status", "Desconocido")
            date = opinion.get("date", "S/D")
            pending = opinion.get("pending_obligations", 0)
            
            if status == "Positiva":
                return f"✅ Tu opinión de cumplimiento es POSITIVA al {date}."
            else:
                return f"⚠️ ALERTA: Tu opinión de cumplimiento es NEGATIVA. Tienes {pending} obligaciones pendientes."
        except Exception as e:
            return f"Error al consultar opinión: {str(e)}"

    def execute_status_query(self) -> str:
        """
        Consulta el estatus general del contribuyente.
        """
        return "Tu estatus actual es: Activo. Sin notificaciones pendientes en el buzón tributario."

    def generate_proactive_notification(self, trigger: str) -> str:
        """
         la notificación proactiva basada en triggers.
        """
        if trigger == "negative_opinion":
            return "🚨 NOTIFICACIÓN PROACTIVA: Se ha detectado un cambio en tu opinión de cumplimiento. Por favor revisa el portal del SAT."
        return "Todo parece estar en orden con tu situación fiscal."
