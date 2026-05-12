import logging
import threading
import time
from datetime import datetime
from typing import Dict, Any, Optional

from fisco_agent import FiscoAgent
from sat_models import SATAuthCredentials
from vault import Vault

# Logging config
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] FiscoGhost: %(message)s'
)
logger = logging.getLogger("fisco_ghost")

class FiscoGhost:
    """
    El Agente Fantasma de Fisco.
    Opera en segundo plano, escucha eventos de FiscoMind y envía notificaciones proactivas.
    """
    def __init__(self, credentials_id: str):
        self.vault = Vault()
        # Recuperar credenciales desde el vault usando la ID
        creds_data = self.vault.decrypt_credentials(credentials_id)
        self.credentials = SATAuthCredentials(**creds_data)
        
        self.agent = FiscoAgent(self.credentials)
        self.is_running = False
        self._thread = None

    def start(self):
        """Inicia el agente en modo escucha (background)."""
        self.is_running = True
        self._thread = threading.Thread(target=self._background_loop, daemon=True)
        self._thread.start()
        logger.info("👻 FiscoGhost activado y operando en segundo plano.")

    def stop(self):
        self.is_running = False
        if self._thread:
            self._thread.join()
        logger.info("👻 FiscoGhost desactivado.")

    def _background_loop(self):
        """
        Bucle de monitoreo. 
        En un entorno real, esto escucharía un webhook o un queue de FiscoMind.
        Aquí simulamos el chequeo periódico de salud fiscal.
        """
        while self.is_running:
            try:
                logger.info("🔍 FiscoGhost: Monitoreando eventos de FiscoMind...")
                
                # 1. Simular chequeo de Opinión de Cumplimiento cada 24h (o menos para demo)
                # En producción, esto sería disparado por un evento de FiscoMind
                opinion_status = self.agent.execute_compliance_check()
                
                if "⚠️ ALERTA" in opinion_status:
                    self._send_whisper_to_marco(f"🚨 FISCO ALERT: {opinion_status}")
                
                # 2. Simular chequeo de nuevos CFDIs
                # download_status = self.agent.execute_cfdi_download()
                # if "Insight" in download_status:
                #     self._send_whisper_to_marco(f"💡 FISCO INSIGHT: {download_status}")

                # Esperar antes del siguiente ciclo (ej. cada hora)
                time.sleep(3600) 
                
            except Exception as e:
                logger.error(f"Error en el loop de FiscoGhost: {e}")
                time.sleep(60)

    def _send_whisper_to_marco(self, message: str):
        """
        Envía una notificación proactiva a Marco.
        En la arquitectura de OpenClaw, esto se hace vía el sistema de mensajería.
        """
        logger.info(f"📤 Enviando whisper a Marco: {message}")
        # MOCK: Aquí se integraría con el bot de Telegram de Sofía para enviar el mensaje
        # la implementación real llamaría a la API de Telegram o al gateway de OpenClaw
        print(f"\n[WHISPER TO MARCO] {message}\n")

    def process_event(self, event: Dict[str, Any]):
        """
        Entry point para que FiscoMind (el bot) envíe eventos al agente fantasma.
        """
        logger.info(f"📥 Evento recibido de FiscoMind: {event}")
        response = self.agent.handle_telegram_event(event)
        return response

if __name__ == "__main__":
    # Para pruebas rápidas
    # Asumimos que hay una credencial guardada con id 'marco_sat'
    try:
        ghost = FiscoGhost(credentials_id="marco_sat")
        ghost.start()
        
        # Simular un evento entrante de FiscoMind
        mock_event = {"user_id": "marco", "text": "descargar CFDI"}
        print(f"Resultado evento: {ghost.process_event(mock_event)}")
        
        # Mantener vivo el proceso para el loop de fondo
        while True:
            time.sleep(1)
    except Exception as e:
        print(f"Error al iniciar FiscoGhost: {e}")
