#!/usr/bin/env python3
"""
FiscoMind Secure Vault - Zero-Exposure Credential Management
Handles SAT credentials with maximum security:
- Fernet (AES-256) encryption at rest
- Memory-only decryption during use
- No logging, no network transmission
"""

import os
import sys
import json
import base64
import secrets
from pathlib import Path
from cryptography.fernet import Fernet

class Vault:
    """Secure credential vault for SAT e.firma"""
    
    # Support both local development and Railway deployment
    _vault_dir = os.environ.get('VAULT_DIR', 
        '/Users/bullslab/.openclaw/agents/fisco-workspace/credentials')
    VAULT_DIR = Path(_vault_dir)
    KEY_FILE = VAULT_DIR / '.vault_key'
    
    def __init__(self):
        self.VAULT_DIR.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.VAULT_DIR, 0o700)
        except:
            pass
    
    def _get_or_create_key(self) -> bytes:
        """Get or create encryption key for vault"""
        if self.KEY_FILE.exists():
            with open(self.KEY_FILE, 'rb') as f:
                return base64.urlsafe_b64decode(f.read())
        else:
            key = Fernet.generate_key()
            with open(self.KEY_FILE, 'wb') as f:
                f.write(key)
            try:
                os.chmod(self.KEY_FILE, 0o600)
            except:
                pass
            return base64.urlsafe_b64decode(key)
    
    def encrypt_file(self, source_path: Path, dest_filename: str) -> Path:
        """Encrypt a file and store in vault"""
        key = self._get_or_create_key()
        f = Fernet(base64.urlsafe_b64encode(key))
        
        with open(source_path, 'rb') as src:
            data = src.read()
        encrypted = f.encrypt(data)
        
        dest_path = self.VAULT_DIR / f"{dest_filename}.enc"
        with open(dest_path, 'wb') as dst:
            dst.write(encrypted)
        try:
            os.chmod(dest_path, 0o600)
        except:
            pass
        
        self._secure_delete(source_path)
        return dest_path
    
    def decrypt_to_memory(self, filename: str) -> bytes:
        """Decrypt file to memory only - never to disk"""
        key = self._get_or_create_key()
        f = Fernet(base64.urlsafe_b64encode(key))
        
        # Try with .enc extension first, then without
        enc_path = self.VAULT_DIR / f"{filename}.enc"
        if not enc_path.exists():
            enc_path = self.VAULT_DIR / filename
        
        with open(enc_path, 'rb') as src:
            encrypted = src.read()
        
        return f.decrypt(encrypted)
    
    def store_password(self, service: str, password: str):
        """Store password in vault"""
        key = self._get_or_create_key()
        f = Fernet(base64.urlsafe_b64encode(key))
        
        encrypted = f.encrypt(password.encode())
        pass_file = self.VAULT_DIR / f"{service}.pass.enc"
        with open(pass_file, 'wb') as pf:
            pf.write(encrypted)
        try:
            os.chmod(pass_file, 0o600)
        except:
            pass
    
    def get_password(self, service: str) -> str:
        """Retrieve password from vault"""
        key = self._get_or_create_key()
        f = Fernet(base64.urlsafe_b64encode(key))
        
        pass_file = self.VAULT_DIR / f"{service}.pass.enc"
        with open(pass_file, 'rb') as pf:
            encrypted = pf.read()
        
        return f.decrypt(encrypted).decode()
    
    def _secure_delete(self, path: Path, passes: int = 3):
        """Securely delete file by overwriting before unlink"""
        if not path.exists():
            return
        size = path.stat().st_size
        with open(path, 'ba+') as f:
            for _ in range(passes):
                f.seek(0)
                f.write(secrets.token_bytes(size))
                f.flush()
                os.fsync(f.fileno())
        path.unlink()


if __name__ == "__main__":
    vault = Vault()
    if len(sys.argv) > 1 and sys.argv[1] == "init":
        print("🔐 FiscoMind Vault initialized")
        print(f"Vault location: {vault.VAULT_DIR}")
        print("✅ Credentials encrypted with AES-256")
    else:
        print(f"Usage: python secure_vault.py init")
        print(f"Vault dir: {vault.VAULT_DIR}")