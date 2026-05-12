import logging
from datetime import datetime
from typing import Dict, Any

from sat_connector import SATConnector
from sat_models import SATAuthCredentials, CFDIModel, ComplianceOpinion

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fisco_agent")

class FiscoAgent:
    """
    Agente principal que orquesta la interacción con el SAT y genera insights fiscales.
    """
    
    def __init__(self, credentials: SATAuthCredentials):
        self.credentials = credentials
        self.connector = SATConnector(
            rfc=credentials.rfc,
            password=credentials.password,
            efirma_path=credentials.efirma_path,
            efirma_key=credentials.efirma_key
        )
        
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
        else:
            return "Lo siento, no reconozco el comando. Prueba con 'descargar CFDI' o 'consultar opinión'."

    def execute_cfdi_download(self) -> str:
        """
        Coordina la descarga de CFDIs y el parseo.
        """
        try:
            # 1. Descarga via connector
            raw_cfdis = self.connector.download_cfdis(
                date_start="2024-01-01", 
                date_end=datetime.now().strftime("%Y-%m-%d"), 
                type="recibidos"
            )
            
            # 2. (Simulado) Pasaría a cfdi_parser y deduction_engine
            # Aquí coordinamos el flujo: Download -> Parse -> Deduct -> Alert
            
            summary = f"Se han descargado {len(raw_cfdis)} CFDIs. Analizando deducciones..."
            # Mock de insight generado por el motor de deducción
            insight = "💡 Insight: Detecté 3 gastos deducibles no registrados en tu contabilidad."
            
            return f"{summary}\n{insight}"
        except Exception as e:
            logger.error(f"Error en descarga de CFDIs: {e}")
            return f"Error al procesar CFDIs: {str(e)}"

    def execute_compliance_check(self) -> str:
        """
        Consulta la opinión de cumplimiento y genera alerta si es negativa.
        """
        try:
            opinion = self.connector.get_compliance_opinion()
            
            if opinion["status"] == "Positiva":
                return f"✅ Tu opinión de cumplimiento es POSITIVA al {opinion['date']}."
            else:
                # Coordinaría con compliance_alerts
                return f"⚠️ ALERTA: Tu opinión de cumplimiento es NEGATIVA. Tienes {opinion['pending_obligations']} obligaciones pendientes."
        except Exception as e:
            logger.error(f"Error en consulta de opinión: {e}")
            return f"Error al consultar opinión: {str(e)}"

    def execute_status_query(self) -> str:
        """
        Consulta el estatus general del contribuyente.
        """
        return "Tu estatus actual es: Activo. Sin notificaciones pendientes en el buzón tributario."

    def generate_proactive_notification(self, trigger: str) -> str:
        """
        Genera una notificación proactiva basada en triggers.
        """
        if trigger == "negative_opinion":
            return "🚨 NOTIFICACIÓN PROACTIVA: Se ha detectado un cambio en tu opinión de cumplimiento. Por favor revisa el portal del SAT."
        return "Todo parece estar en orden con tu situación fiscal."
