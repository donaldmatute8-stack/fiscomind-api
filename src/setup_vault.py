#!/usr/bin/env python3
"""
FiscoMind Vault Setup - Railway Deployment
Copia archivos de vault encriptados al directorio de Railway
USO: python3 setup_vault.py [directorio_local_vault]

Ejemplo:
  python3 setup_vault.py /Users/bullslab/.openclaw/agents/sofia-workspace/fiscomind-api/credentials
"""

import os
import sys
import shutil
from pathlib import Path


def setup_vault(source_dir: str = None):
    """Copia archivos de vault a Railway"""

    if source_dir is None:
        # Default para desarrollo local
        source_dir = Path(__file__).parent.parent / "credentials"
    else:
        source_dir = Path(source_dir)

    target_dir = Path(os.environ.get("VAULT_DIR", "/app/credentials"))

    print(f"📁 Vault Source: {source_dir}")
    print(f"📁 Vault Target: {target_dir}")

    # Archivos a copiar (ya encriptados, seguros)
    files_to_copy = [
        ".vault_key",
        "fiel_cer.enc",
        "fiel_key.enc",
        "fiel_sat.pass.enc",
        "sat_password.pass.enc",
    ]

    # Crear directorio target
    target_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    for fname in files_to_copy:
        src = source_dir / fname
        dst = target_dir / fname

        if src.exists():
            shutil.copy2(src, dst)
            print(f"  ✅ {fname}")
            copied += 1
        else:
            print(f"  ⚠️ No encontrado: {fname}")

    print(f"\n✅ {copied}/{len(files_to_copy)} archivos copiados")

    if copied < len(files_to_copy):
        print("\n⚠️ ADVERTENCIA: Faltan archivos de vault")
        print("   Asegúrate de que la FIEL esté configurada localmente primero")
        return False

    return True


if __name__ == "__main__":
    source = sys.argv[1] if len(sys.argv) > 1 else None
    success = setup_vault(source)
    sys.exit(0 if success else 1)
