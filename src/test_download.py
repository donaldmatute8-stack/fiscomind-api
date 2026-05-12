import logging
from datetime import datetime
from fisco_agent import FiscoAgent
from sat_models import SATAuthCredentials

# Mock credentials for testing connectivity
credentials = SATAuthCredentials(
    rfc="TESTRFC",
    password="TESTPASSWORD",
    efirma_path="/tmp/test.cer",
    efirma_key="/tmp/test.key"
)

try:
    agent = FiscoAgent(credentials)
    print("Agente inicializado. Ejecutando descarga de CFDIs...")
    result = agent.execute_cfdi_download()
    print(f"Resultado:\n{result}")
except Exception as e:
    print(f"Error técnico: {e}")
