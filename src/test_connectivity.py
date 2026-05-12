import logging
from sat_connector import SATConnector

# Mock RFC for testing
rfc_test = "TESTRFC123"

try:
    print(f"Iniciando prueba de conexión al SAT para RFC: {rfc_test}...")
    connector = SATConnector(rfc=rfc_test)
    
    # Intentar autenticar (esto valida si el Vault está funcionando)
    if connector.authenticate():
        print("✅ Autenticación exitosa (Credenciales recuperadas del Vault).")
        
        # Probar descarga de CFDIs
        cfdis = connector.download_cfdis(date_start="2026-01-01", date_end="2026-05-08")
        print(f"✅ Descarga exitosa. Se encontraron {len(cfdis)} CFDIs.")
        for cfdi in cfdis[:2]:
            print(f"   - Folio: {cfdi['folio']} | Monto: {cfdi['monto']}")
        
        # Probar Opinión de Cumplimiento
        opinion = connector.get_compliance_opinion()
        print(f"✅ Opinión de cumplimiento: {opinion['status']}")
    else:
        print("❌ Error: La autenticación falló. Verifica el Vault.")

except Exception as e:
    print(f"❌ Error técnico durante la prueba: {e}")
