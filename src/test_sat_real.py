import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent))
from secure_vault import Vault

def run_test():
    vault = Vault()
    rfc = "MUTM8610091NA"
    
    print(f"--- Iniciando Prueba SAT Real para RFC: {rfc} ---")
    
    # 1. Verificar y preparar password en vault (Simulación de carga inicial si no existe)
    try:
        vault.get_password("sat_password")
        print("✅ Password encontrado en vault.")
    except Exception:
        print("⚠️ Password no encontrado. Creando password de prueba en vault...")
        vault.store_password("sat_password", "MarcoSecurePass2026!")
    
    # 2. Instanciar el nuevo SATConnector
    from sat_connector import SATConnector
    connector = SATConnector(rfc=rfc, vault_filename="fiel_key", password_service="sat_password")
    
    # 3. Probar Autenticación
    if connector.authenticate():
        print("✅ Autenticación exitosa con credenciales reales del vault.")
        
        # 4. Descargar CFDIs
        cfdis = connector.download_cfdis("2026-01-01", "2026-05-08")
        print(f"✅ CFDIs descargados: {len(cfdis)}")
        for cfdi in cfdis:
            print(f"   - {cfdi['folio']} | {cfdi['monto']} | {cfdi['fecha']}")
            
        # 5. Opinión de cumplimiento
        opinion = connector.get_compliance_opinion()
        print(f"✅ Opinión de cumplimiento: {opinion['status']} (Obligaciones pendientes: {opinion['pending_obligations']})")
        
        connector.close_session()
        print("--- PRUEBA COMPLETADA EXITOSAMENTE ---")
    else:
        print("❌ Error: La autenticación falló.")
        sys.exit(1)

if __name__ == "__main__":
    run_test()
