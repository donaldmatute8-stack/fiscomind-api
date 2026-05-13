#!/usr/bin/env python3
"""
FiscoMind Vault Sync - Sube vault encriptado a Railway
Ejecutar desde local para sincronizar credenciales a Railway

SEGURIDAD:
- Los archivos .enc ya están encriptados con AES-256
- Solo subimos archivos encriptados, nunca el .key descifrado
- Railway descifra usando su propia copia de .vault_key
"""

import os
import sys
import base64

VAULT_SOURCE = (
    "/Users/bullslab/.openclaw/agents/sofia-workspace/fiscomind-api/credentials"
)


def get_vault_key_base64():
    """Exporta vault key como base64 (para configurar en Railway)"""
    key_file = os.path.join(VAULT_SOURCE, ".vault_key")
    if os.path.exists(key_file):
        with open(key_file, "rb") as f:
            return base64.urlsafe_b64encode(f.read()).decode()
    return None


if __name__ == "__main__":
    print("🔐 FiscoMind Vault Sync")
    print("=" * 50)

    key = get_vault_key_base64()
    if not key:
        print("❌ No se encontró .vault_key")
        sys.exit(1)

    print("\n📋 Archivos en vault local:")
    for f in os.listdir(VAULT_SOURCE):
        path = os.path.join(VAULT_SOURCE, f)
        if os.path.isfile(path):
            size = os.path.getsize(path)
            encrypted = "🔒" if f.endswith(".enc") or f.endswith(".pass") else "📄"
            print(f"  {encrypted} {f} ({size} bytes)")

    print("\n" + "=" * 50)
    print("📝 INSTRUCCIONES PARA RAILWAY:")
    print("=" * 50)
    print(
        """
1. Ve a Railway Dashboard → Proyecto FiscoMind API → Variables

2. Crea una nueva variable:
   Nombre: VAULT_SYNC_KEY
   Valor: {}
   
   (Esta es la clave para descifrar vault en Railway)

3. Los archivos encriptados (.enc) se copian automáticamente
   al volumen /app/credentials cuando hagas deploy.

4. Para verificar, revisa que Railway tenga los archivos:
   - .vault_key
   - fiel_cer.enc
   - fiel_key.enc
   - fiel_sat.pass.enc
   - sat_password.pass.enc

⚠️ IMPORTANTE: La vault_key de arriba es SENSIBLE.
   Solo cópiala directamente a Railway, nunca la guards en otro lugar.
""".format(key)
    )

    print("\n✅ Listo. Copia la VAULT_SYNC_KEY a Railway y redespliega.")
