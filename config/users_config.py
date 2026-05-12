"""
User Configuration for FiscoMind Mini App
Handles multiple users with encrypted vault credentials

Each user has:
  - A JSON config file with their RFC and preferences
  - Encrypted SAT FIEL credentials in the vault (fiel_key_{user_id}, fiel_cer_{user_id}, fiel_sat_{user_id})
  
The default user ('marco_test') uses the existing vault credentials (fiel_key, fiel_cer, fiel_sat)
for backward compatibility during testing.
"""
import os
import sys
import json
import re
from pathlib import Path
from typing import Dict, Optional, Any

sys.path.insert(0, '/Users/bullslab/.openclaw/agents/fisco-workspace/src')
from secure_vault import Vault


def validate_rfc(rfc: str) -> bool:
    """Validate Mexican RFC format (12 or 13 chars)"""
    if not rfc:
        return False
    rfc_clean = rfc.upper().strip()
    # 12 for moral persons, 13 for physical persons
    return len(rfc_clean) in [12, 13] and re.match(r'^[A-Z&Ñ]{3,4}[0-9]{6}[A-Z0-9]{3}$', rfc_clean) is not None


class UserConfig:
    """Manages user-specific SAT credentials and settings"""
    
    BASE_DIR = Path('/Users/bullslab/.openclaw/agents/sofia-workspace/fiscomind/config/users')
    
    def __init__(self, user_id: str = None):
        self.user_id = user_id or os.getenv('FISCOMIND_USER', 'default')
        self.vault = Vault()
        self._config_dir = self.BASE_DIR
        self._config_dir.mkdir(parents=True, exist_ok=True)
        self._user_file = self._config_dir / f"{self.user_id}.json"
    
    def get_user_data(self) -> Dict[str, Any]:
        """Get stored user configuration"""
        if self._user_file.exists():
            return json.loads(self._user_file.read_text())
        return {}
    
    def save_user_data(self, data: Dict[str, Any]):
        """Save user configuration"""
        self._user_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    
    def get_sat_credentials(self) -> Optional[Dict[str, Any]]:
        """
        Get SAT FIEL credentials from encrypted vault
        
        For the default test user ('marco_test'), uses the existing vault entries:
          - fiel_key, fiel_cer, fiel_sat
        
        For other users, uses:
          - fiel_key_{user_id}, fiel_cer_{user_id}, fiel_sat_{user_id}
        """
        try:
            # Determine vault keys based on user
            if self.user_id == 'marco_test':
                # Use existing vault entries (backward compatibility)
                key_name = 'fiel_key'
                cer_name = 'fiel_cer'
                pass_name = 'fiel_sat'
            else:
                key_name = f'fiel_key_{self.user_id}'
                cer_name = f'fiel_cer_{self.user_id}'
                pass_name = f'fiel_sat_{self.user_id}'
            
            password = self.vault.get_password(pass_name)
            key_data = self.vault.decrypt_to_memory(key_name)
            cer_data = self.vault.decrypt_to_memory(cer_name)
            
            user_data = self.get_user_data()
            rfc = user_data.get('rfc', '')
            
            return {
                'rfc': rfc,
                'password': password,
                'key_data': key_data,
                'cer_data': cer_data
            }
        except Exception as e:
            print(f"Error loading SAT credentials for {self.user_id}: {e}")
            return None
    
    def set_user_rfc(self, rfc: str):
        """Set user's RFC with validation"""
        rfc_clean = rfc.upper().strip()
        if not validate_rfc(rfc_clean):
            raise ValueError(f"RFC inválido: {rfc}")
        data = self.get_user_data()
        data['rfc'] = rfc_clean
        self.save_user_data(data)
    
    def is_configured(self) -> bool:
        """Check if user has SAT credentials configured in vault"""
        return self.get_sat_credentials() is not None
    
    def store_fiel(self, key_path: str, cer_path: str, password: str):
        """
        Store FIEL credentials in encrypted vault for this user
        
        Args:
            key_path: Path to .key file (private key)
            cer_path: Path to .cer file (certificate)
            password: Password for the .key file
        """
        # Determine vault keys
        if self.user_id == 'marco_test':
            key_name = 'fiel_key'
            cer_name = 'fiel_cer'
            pass_name = 'fiel_sat'
        else:
            key_name = f'fiel_key_{self.user_id}'
            cer_name = f'fiel_cer_{self.user_id}'
            pass_name = f'fiel_sat_{self.user_id}'
        
        # Encrypt and store
        self.vault.encrypt_file(key_name, key_path)
        self.vault.encrypt_file(cer_name, cer_path)
        self.vault.store_password(pass_name, password)
        
        print(f"✅ FIEL stored for user '{self.user_id}'")


class MultiUserManager:
    """Manages multiple users for the mini app"""
    
    def __init__(self):
        self._config_dir = UserConfig.BASE_DIR
        self._config_dir.mkdir(parents=True, exist_ok=True)
    
    def list_users(self) -> list:
        """List all configured users"""
        return [f.stem for f in self._config_dir.glob('*.json')]
    
    def create_user(self, user_id: str, rfc: str) -> UserConfig:
        """Create new user configuration with RFC validation"""
        if not validate_rfc(rfc):
            raise ValueError(f"RFC inválido: {rfc}")
        config = UserConfig(user_id)
        config.set_user_rfc(rfc)
        return config
    
    def get_user(self, user_id: str) -> Optional[UserConfig]:
        """Get user configuration"""
        config = UserConfig(user_id)
        if config._user_file.exists():
            return config
        return None
    
    def delete_user(self, user_id: str):
        """Delete user configuration (does NOT delete vault entries)"""
        config = UserConfig(user_id)
        if config._user_file.exists():
            config._user_file.unlink()
            return True
        return False