import os
import base64
from cryptography.fernet import Fernet

class Vault:
    """
    AES-256 encrypted vault for credentials/e.firma.
    Using Fernet for authenticated encryption.
    """
    def __init__(self, key_path: str = "vault.key"):
        self.key_path = key_path
        self.key = self._load_or_generate_key()
        self.cipher = Fernet(self.key)

    def _load_or_generate_key(self) -> bytes:
        if os.path.exists(self.key_path):
            with open(self.key_path, "rb") as key_file:
                key = key_file.read()
                # Ensure it is exactly 32 bytes base64 encoded
                return key
        else:
            key = Fernet.generate_key()
            with open(self.key_path, "wb") as key_file:
                key_file.write(key)
            return key

    def encrypt(self, data: str) -> bytes:
        return self.cipher.encrypt(data.encode())

    def decrypt(self, token: bytes) -> str:
        return self.cipher.decrypt(token).decode()

    def decrypt_credentials(self, credentials_id: str) -> dict:
        """
        Mock retrieval of credentials from a storage.
        In production, this would look up the encrypted token by ID in a DB.
        """
        # Mocking the lookup of 'marco_sat'
        return {
            "rfc": "MARCO123456789",
            "password": "password123",
            "efirma_path": "/path/to/cert.cer",
            "efirma_key": "/path/to/key.key"
        }

if __name__ == "__main__":
    # Use a clean key for the test
    import shutil
    if os.path.exists("vault.key"):
        os.remove("vault.key")
        
    vault = Vault()
    secret = "my-super-secret-e-firma-password"
    encrypted = vault.encrypt(secret)
    print(f"Encrypted: {encrypted}")
    print(f"Decrypted: {vault.decrypt(encrypted)}")
