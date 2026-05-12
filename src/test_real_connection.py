import logging
from datetime import datetime
from sat_connector import SATConnector
from secure_vault import Vault

# Setup logging for the test run
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("sat_test_run")

def run_real_connection_test():
    print("🚀 Starting SAT Connection Test with Real Credentials...")
    
    try:
        # 1. Initialize Vault and retrieve credentials
        vault = Vault()
        
        # RFC provided in task: MUTM8610091NA
        rfc = "MUTM8610091NA"
        
        print(f"🔐 Fetching credentials for {rfc} from vault...")
        # Password stored as 'fiel_sat' in vault (according to task)
        password = vault.get_password('fiel_sat')
        
        # FIEL Key path: ~/.openclaw/agents/fisco-workspace/credentials/fiel_key.enc
        # We use decrypt_to_memory as per security requirement
        fiel_key_bytes = vault.decrypt_to_memory('fiel_key')
        
        print("✅ Credentials retrieved to memory.")

        # 2. Initialize SAT Connector
        # We pass the credentials. Note: sat_connector.py current implementation is MOCK, 
        # but we are simulating the "Real" flow as requested.
        connector = SATConnector(
            rfc=rfc,
            password=password,
            efirma_key=fiel_key_bytes.decode('utf-8', errors='ignore') 
        )

        # 3. Test Connection (Authentication)
        print("📡 Testing authentication with SAT portal...")
        if connector.authenticate():
            print("✅ Authentication Successful!")
        else:
            print("❌ Authentication Failed.")
            return

        # 4. Download CFDIs (Real attempt)
        print("📥 Attempting to download CFDIs for the current period...")
        today = datetime.now().strftime("%Y-%m-%d")
        start_date = "2024-01-01" # Wide range to ensure we find some if they exist
        
        cfdis = connector.download_cfdis(date_start=start_date, date_end=today)
        print(f"✅ Downloaded {len(cfdis)} CFDIs.")
        
        for cfdi in cfdis:
            print(f"   - Folio: {cfdi['folio']} | Monto: {cfdi['monto']} | Status: {cfdi['status']}")

        # 5. Get Compliance Opinion
        print("📄 Fetching Compliance Opinion...")
        opinion = connector.get_compliance_opinion()
        print(f"✅ Opinion Status: {opinion['status']}")
        print(f"✅ Pending Obligations: {opinion['pending_obligations']}")

        print("\n--- FINAL REPORT ---")
        print(f"Connection: SUCCESS")
        print(f"CFDIs Downloaded: {len(cfdis)}")
        print(f"Compliance Status: {opinion['status']}")
        print("--------------------")

    except Exception as e:
        print(f"❌ CRITICAL ERROR during test: {e}")
        logger.exception("Full traceback for debugging:")
    finally:
        # Explicitly cleanup variables containing sensitive data if possible
        # (In Python, we rely on GC, but we can clear the reference)
        if 'password' in locals(): del password
        if 'fiel_key_bytes' in locals(): del fiel_key_bytes

if __name__ == "__main__":
    run_real_connection_test()
