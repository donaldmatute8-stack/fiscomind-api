"""
Rabbitty Web3 Integration for FiscoMind
Connects FiscoMind fiscal data with Rabbitty Identity & Rewards System
"""
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("rabbitty_integration")


@dataclass
class IdentityData:
    """Rabbitty Identity structure"""
    token_id: int
    username: str
    level: int
    experience: int
    power: int
    rfc: str
    achievements: List[str]
    equipped_accessories: List[int]
    created_at: str
    last_updated: str


@dataclass
class RewardCalculation:
    """Calculated rewards based on fiscal activity"""
    base_reward: float
    level_bonus: float
    streak_bonus: float
    total_reward: float
    tax_optimization_score: int
    cfdi_count: int
    compliance_score: int


class RabbittyFiscoBridge:
    """
    Bridge between FiscoMind fiscal data and Rabbitty Web3 identity
    
    This class:
    - Calculates rewards based on fiscal activity
    - Generates identity based on RFC
    - Tracks achievements from fiscal milestones
    - Provides APIs for micro SaaS integration
    """
    
    def __init__(self, rfc: str, name: str):
        self.rfc = rfc
        self.name = name
        self.cfdis = self._load_cfdis()
        self.identity: Optional[IdentityData] = None
        
    def _load_cfdis(self) -> List[Dict]:
        """Load CFDIs from metadata"""
        try:
            metadata_path = Path(__file__).parent.parent / "data/cfdis/metadata.json"
            if metadata_path.exists():
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('cfdis', [])
        except Exception as e:
            logger.error(f"Error loading CFDIs: {e}")
        return []
    
    def calculate_fiscal_score(self) -> Dict[str, Any]:
        """
        Calculate comprehensive fiscal health score
        Used for Rabbitty XP and rewards
        """
        if not self.cfdis:
            return {
                "score": 0,
                "level": 1,
                "deduction_ratio": 0,
                "compliance_status": "No data"
            }
        
        # Calculate metrics
        total_monto = sum(c.get('monto', 0) for c in self.cfdis)
        vigentes = sum(1 for c in self.cfdis if c.get('estatus') == '1')
        total_cfdis = len(self.cfdis)
        
        # Deduction ratio (assuming monthly income estimate)
        estimated_monthly = total_monto / max(1, total_cfdis) * 10  # Rough estimate
        deduction_ratio = total_monto / max(estimated_monthly, 1)
        
        # Compliance score
        compliance_score = (vigentes / max(total_cfdis, 1)) * 100
        
        # Calculate level (1-100)
        base_score = min(total_monto / 100, 50)  # Max 50 points from amount
        compliance_points = compliance_score * 0.3  # Max 30 points
        volume_points = min(total_cfdis * 2, 20)  # Max 20 points from volume
        
        total_score = base_score + compliance_points + volume_points
        level = max(1, int(total_score / 10))
        
        return {
            "score": round(total_score, 2),
            "level": level,
            "total_monto": total_monto,
            "vigentes": vigentes,
            "total_cfdis": total_cfdis,
            "deduction_ratio": round(deduction_ratio * 100, 2),
            "compliance_score": round(compliance_score, 2),
            "compliance_status": "Excelente" if compliance_score >= 95 else "Bueno" if compliance_score >= 80 else "Regular"
        }
    
    def calculate_rewards(self) -> RewardCalculation:
        """
        Calculate Rabbitty rewards based on fiscal activity
        """
        fiscal_score = self.calculate_fiscal_score()
        
        # Base reward from fiscal volume
        base_reward = fiscal_score["total_monto"] * 0.001  # 0.1% of fiscal volume
        
        # Level bonus (higher level = higher multiplier)
        level_multiplier = 1 + (fiscal_score["level"] * 0.02)  # 2% per level
        level_bonus = base_reward * (fiscal_score["level"] * 0.02)
        
        # Compliance streak bonus
        compliance_streak = 1.0  # Would track from historical data
        streak_bonus = base_reward * (compliance_streak - 1)
        
        # Total
        total_reward = base_reward * level_multiplier
        
        # Tax optimization score (based on deduction ratio)
        tax_score = min(fiscal_score["deduction_ratio"], 100)
        
        return RewardCalculation(
            base_reward=round(base_reward, 2),
            level_bonus=round(level_bonus, 2),
            streak_bonus=round(streak_bonus, 2),
            total_reward=round(total_reward, 2),
            tax_optimization_score=int(tax_score),
            cfdi_count=fiscal_score["total_cfdis"],
            compliance_score=int(fiscal_score["compliance_score"])
        )
    
    def generate_achievements(self) -> List[Dict[str, Any]]:
        """
        Generate achievements based on fiscal milestones
        """
        achievements = []
        fiscal = self.calculate_fiscal_score()
        
        # Volume achievements
        if fiscal["total_cfdis"] >= 1:
            achievements.append({
                "id": "first_cfdi",
                "name": "Primer CFDI",
                "description": "Descargaste tu primer CFDI",
                "xp": 100,
                "icon": "📄"
            })
        
        if fiscal["total_cfdis"] >= 10:
            achievements.append({
                "id": "cfdi_collector",
                "name": "Coleccionista",
                "description": "Acumulaste 10 CFDIs",
                "xp": 500,
                "icon": "📚"
            })
        
        if fiscal["total_cfdis"] >= 50:
            achievements.append({
                "id": "cfdi_master",
                "name": "Maestro Fiscal",
                "description": "Acumulaste 50 CFDIs",
                "xp": 2000,
                "icon": "🏆"
            })
        
        # Compliance achievements
        if fiscal["compliance_score"] >= 95:
            achievements.append({
                "id": "compliance_expert",
                "name": "Cumplimiento Perfecto",
                "description": "95%+ de CFDIs vigentes",
                "xp": 1000,
                "icon": "✅"
            })
        
        # Amount achievements
        if fiscal["total_monto"] >= 10000:
            achievements.append({
                "id": "big_saver",
                "name": "Gran Ahorrador",
                "description": "Acumulaste $10,000+ en deducciones",
                "xp": 1500,
                "icon": "💰"
            })
        
        # Tax optimization
        if fiscal["deduction_ratio"] >= 50:
            achievements.append({
                "id": "tax_optimizer",
                "name": "Optimizador Fiscal",
                "description": "50%+ de ratio de deducción",
                "xp": 2000,
                "icon": "🧠"
            })
        
        return achievements
    
    def create_or_update_identity(self) -> IdentityData:
        """
        Create or update Rabbitty identity based on fiscal data
        """
        fiscal = self.calculate_fiscal_score()
        rewards = self.calculate_rewards()
        achievements = self.generate_achievements()
        
        # Create username from RFC
        username = f"fisco_{self.rfc[-8:].lower()}"
        
        # Calculate XP from fiscal score
        xp = int(fiscal["score"] * 10) + sum(a["xp"] for a in achievements)
        
        # Calculate level from XP
        level = max(1, int(xp / 1000))
        
        # Calculate power
        base_power = 100
        level_bonus = (level - 1) * 10
        compliance_bonus = fiscal["compliance_score"] / 10
        power = int(base_power + level_bonus + compliance_bonus)
        
        self.identity = IdentityData(
            token_id=hash(self.rfc) % 1000000,  # Simulated token ID
            username=username,
            level=level,
            experience=xp,
            power=power,
            rfc=self.rfc,
            achievements=[a["name"] for a in achievements],
            equipped_accessories=[],
            created_at=datetime.now().isoformat(),
            last_updated=datetime.now().isoformat()
        )
        
        return self.identity
    
    def get_identity_summary(self) -> str:
        """
        Get formatted identity summary for chat
        """
        if not self.identity:
            self.create_or_update_identity()
        
        rewards = self.calculate_rewards()
        achievements = self.generate_achievements()
        
        summary = f"""
🎮 **Tu Identidad Rabbitty**

👤 **{self.identity.username}**
🎚️ Nivel: {self.identity.level}
⭐ XP: {self.identity.experience:,}
⚡ Poder: {self.identity.power}

📊 **Estadísticas Fiscales:**
• RFC: `{self.rfc}`
• CFDIs: {rewards.cfdi_count}
• Score de cumplimiento: {rewards.compliance_score}%
• Optimización fiscal: {rewards.tax_optimization_score}%

💰 **Recompensas:**
• Base: {rewards.base_reward:.2f} BZ
• Bonus nivel: {rewards.level_bonus:.2f} BZ
• Total disponible: {rewards.total_reward:.2f} BZ

🏆 **Logros ({len(achievements)}):**
"""
        
        for ach in achievements[:5]:
            summary += f"{ach['icon']} {ach['name']} (+{ach['xp']} XP)\n"
        
        summary += f"""
💡 **Próximos objetivos:**
• Sube a nivel {self.identity.level + 1}: +500 XP
• Acumula 10 CFDIs más: +1000 XP
• Mejora tu score de cumplimiento

Para reclamar recompensas, conecta tu wallet!
"""
        
        return summary


class RabbittyMicroSaaSAPI:
    """
    Micro SaaS API for internal Rabbitty services
    Can be exposed as REST API for other services
    """
    
    def __init__(self):
        self.bridges: Dict[str, RabbittyFiscoBridge] = {}
    
    def register_user(self, rfc: str, name: str) -> Dict:
        """Register a new user"""
        bridge = RabbittyFiscoBridge(rfc, name)
        self.bridges[rfc] = bridge
        
        identity = bridge.create_or_update_identity()
        rewards = bridge.calculate_rewards()
        
        return {
            "status": "registered",
            "rfc": rfc,
            "username": identity.username,
            "level": identity.level,
            "total_reward": rewards.total_reward,
            "achievements": len(bridge.generate_achievements())
        }
    
    def get_user_rewards(self, rfc: str) -> Dict:
        """Get rewards for a user"""
        if rfc not in self.bridges:
            return {"error": "User not registered"}
        
        bridge = self.bridges[rfc]
        rewards = bridge.calculate_rewards()
        
        return {
            "rfc": rfc,
            "base_reward": rewards.base_reward,
            "level_bonus": rewards.level_bonus,
            "total_reward": rewards.total_reward,
            "cfdi_count": rewards.cfdi_count,
            "compliance_score": rewards.compliance_score,
            "tax_optimization_score": rewards.tax_optimization_score
        }
    
    def claim_rewards(self, rfc: str, wallet_address: str) -> Dict:
        """Claim rewards to wallet"""
        if rfc not in self.bridges:
            return {"error": "User not registered"}
        
        rewards = self.bridges[rfc].calculate_rewards()
        
        # In real implementation, this would interact with BunzToken contract
        return {
            "status": "claimed",
            "rfc": rfc,
            "wallet": wallet_address,
            "amount": rewards.total_reward,
            "tx_hash": f"0x{hash(rfc + wallet_address) % 10**16:016x}"  # Simulated
        }
    
    def get_leaderboard(self, limit: int = 10) -> List[Dict]:
        """Get top users by rewards"""
        users = []
        for rfc, bridge in self.bridges.items():
            rewards = bridge.calculate_rewards()
            identity = bridge.create_or_update_identity()
            users.append({
                "rfc": rfc,
                "username": identity.username,
                "level": identity.level,
                "total_reward": rewards.total_reward,
                "power": identity.power
            })
        
        return sorted(users, key=lambda x: x["total_reward"], reverse=True)[:limit]
    
    def sync_fiscal_data(self, rfc: str) -> Dict:
        """Sync fiscal data and update identity"""
        if rfc not in self.bridges:
            return {"error": "User not registered"}
        
        bridge = self.bridges[rfc]
        bridge.cfdis = bridge._load_cfdis()  # Reload
        
        identity = bridge.create_or_update_identity()
        rewards = bridge.calculate_rewards()
        
        return {
            "status": "synced",
            "rfc": rfc,
            "cfdis_count": rewards.cfdi_count,
            "level": identity.level,
            "xp": identity.experience,
            "new_rewards": rewards.total_reward
        }


# Singleton for reuse
_rabbitty_api: Optional[RabbittyMicroSaaSAPI] = None


def get_rabbitty_api() -> RabbittyMicroSaaSAPI:
    """Get or create Rabbitty API singleton"""
    global _rabbitty_api
    if _rabbitty_api is None:
        _rabbitty_api = RabbittyMicroSaaSAPI()
    return _rabbitty_api


# Convenience functions for bot integration
def get_fisco_identity_summary(rfc: str, name: str) -> str:
    """Get formatted summary for Telegram bot"""
    bridge = RabbittyFiscoBridge(rfc, name)
    return bridge.get_identity_summary()


def calculate_rewards_for_user(rfc: str, name: str) -> Dict:
    """Calculate rewards for a user"""
    bridge = RabbittyFiscoBridge(rfc, name)
    rewards = bridge.calculate_rewards()
    return {
        "total": rewards.total_reward,
        "base": rewards.base_reward,
        "level_bonus": rewards.level_bonus,
        "achievements": len(bridge.generate_achievements())
    }
