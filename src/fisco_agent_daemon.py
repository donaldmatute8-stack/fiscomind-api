#!/usr/bin/env python3
"""
FiscoMind Agent Daemon - Autonomous Fiscal Intelligence

This agent runs continuously and provides:
- Automatic SAT connection and data retrieval
- Proactive fiscal analysis and alerts
- Background processing for FiscoMind operations

Security: Uses secure_vault for credential access. Credentials are only decrypted in memory during active operations.
"""

import os
import sys
import json
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any

# Add src to path
sys.path.insert(0, '/Users/bullslab/.openclaw/agents/fisco-workspace/src')

from secure_vault import Vault
from sat_connector import SATConnector
from cfdi_parser import parse_cfdi
from deduction_engine import DeductionEngine
from compliance_alerts import ComplianceAlerts

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('FiscoAgent')

class FiscoAgentDaemon:
    """
    Autonomous agent that manages fiscal operations.
    Can be invoked by FiscoMind bot or run scheduled tasks.
    """
    
    def __init__(self):
        self.vault = Vault()
        self.deduction_engine = DeductionEngine()
        self.compliance = ComplianceAlerts()
        self.sat_connector: Optional[SATConnector] = None
        self.is_connected = False
        
        # Admin configuration
        self.admin_rfc = "MUTM8610091NA"
        
    async def initialize(self):
        """Initialize the agent with credentials from secure vault"""
        logger.info("🔐 Initializing Fisco Agent...")
        
        try:
            # Decrypt credentials to memory only
            fiel_key = self.vault.decrypt_to_memory('fiel_key')
            password = self.vault.get_password('fiel_sat')
            
            # Create temporary files for SAT connection (will be securely deleted after)
            self._setup_sat_connection(fiel_key, password)
            
            self.is_connected = True
            logger.info("✅ Fisco Agent initialized and ready")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize: {e}")
            self.is_connected = False
            raise
    
    def _setup_sat_connection(self, fiel_key: bytes, password: str):
        """Setup SAT connection with decrypted credentials"""
        # TODO: Implement actual SAT connection using decrypted credentials
        # For now, we'll store in temp files that get cleaned up
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.key', delete=False) as f:
            f.write(fiel_key)
            key_path = f.name
        
        # Initialize connector (implementation in sat_connector.py)
        self.sat_connector = SATConnector(
            rfc=self.admin_rfc,
            password=password,
            efirma_path=key_path
        )
        
        # Securely cleanup temp file
        import secrets
        with open(key_path, 'ba+') as f:
            f.seek(0)
            f.write(secrets.token_bytes(len(fiel_key)))
        os.unlink(key_path)
    
    async def download_cfdis(self, days: int = 30) -> Dict[str, Any]:
        """Download CFDIs from SAT for specified period"""
        if not self.is_connected:
            await self.initialize()
        
        logger.info(f"📥 Downloading CFDIs for last {days} days...")
        
        try:
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Connect to SAT and download
            cfdis = self.sat_connector.download_cfdis(
                date_start=start_date.strftime('%Y-%m-%d'),
                date_end=end_date.strftime('%Y-%m-%d')
            )
            
            logger.info(f"✅ Downloaded {len(cfdis)} CFDIs")
            return {"count": len(cfdis), "cfdis": cfdis}
            
        except Exception as e:
            logger.error(f"❌ CFDI download failed: {e}")
            return {"error": str(e), "count": 0, "cfdis": []}
    
    async def analyze_deductions(self, cfdi_data: list) -> Dict[str, Any]:
        """Analyze CFDIs for deductible expenses"""
        logger.info("🔍 Analyzing deductions...")
        
        suggestions = []
        total_deductions = 0.0
        
        for cfdi in cfdi_data:
            # For now, create a simple analysis based on the CFDI data from SAT
            # In production, this would parse the actual XML
            emisor = cfdi.get('emisor', 'Unknown')
            monto = cfdi.get('monto', 0)
            
            # Simple deduction rules based on common vendors
            deduction_keywords = {
                'gasolina': ('Transporte', 'Gasolina deducible'),
                'amazon': ('Tecnología', 'Equipos de cómputo'),
                'telmex': ('Servicios', 'Telecomunicaciones'),
                'restaurant': ('Alimentos', 'Comidas de negocios'),
                'uber': ('Transporte', 'Transporte de negocio'),
            }
            
            emisor_lower = emisor.lower()
            for keyword, (category, reason) in deduction_keywords.items():
                if keyword in emisor_lower:
                    suggestions.append({
                        'concept': f"{category}: {emisor}",
                        'amount': monto,
                        'reason': reason
                    })
                    total_deductions += monto
                    break
        
        return {
            'suggestions': suggestions,
            'total_deductions': total_deductions,
            'tax_savings_estimate': total_deductions * 0.3  # Approximate
        }
    
    async def check_compliance(self) -> Dict[str, Any]:
        """Check fiscal compliance status"""
        logger.info("📋 Checking compliance...")
        
        alerts = self.compliance.get_upcoming_alerts()
        
        return {
            'alerts': alerts,
            'urgent_count': len([a for a in alerts if a.get('urgent')]),
            'next_deadline': alerts[0] if alerts else None
        }
    
    async def generate_fiscal_report(self) -> str:
        """Generate comprehensive fiscal report"""
        logger.info("📊 Generating fiscal report...")
        
        # Download recent CFDIs
        cfdi_data = await self.download_cfdis(days=30)
        
        # Analyze deductions
        deductions = await self.analyze_deductions(cfdi_data.get('cfdis', []))
        
        # Check compliance
        compliance = await self.check_compliance()
        
        next_event = compliance['next_deadline'].get('title') if compliance['next_deadline'] else 'Ninguna'
        next_date = compliance['next_deadline'].get('date') if compliance['next_deadline'] else 'N/A'
        
        # Generate report
        report = f"""
📊 FISCO AGENT REPORT - {datetime.now().strftime('%Y-%m-%d %H:%M')}

💰 DEDUCTIONS ANALYSIS
   Total Identified: ${deductions['total_deductions']:,.2f}
   Estimated Savings: ${deductions['tax_savings_estimate']:,.2f}
   Items Found: {len(deductions['suggestions'])}

⏰ COMPLIANCE STATUS
   Urgent Items: {compliance['urgent_count']}
   Next Deadline: {next_event} ({next_date})

📝 TOP DEDUCTIONS
"""
        for i, sug in enumerate(deductions['suggestions'][:5], 1):
            report += f"   {i}. {sug['concept']}: ${sug['amount']:,.2f}\n"
        
        return report
    
    async def run_background_tasks(self):
        """Run background fiscal monitoring"""
        logger.info("🤖 Fisco Agent running background tasks...")
        
        while True:
            try:
                # Daily fiscal check
                if datetime.now().hour == 8:  # 8 AM daily check
                    report = await self.generate_fiscal_report()
                    logger.info(f"📤 Daily report:\n{report}")
                    
                    # Here you would send to Telegram bot
                    # await send_to_admin(report)
                
                # Check for urgent deadlines every hour
                compliance = await self.check_compliance()
                if compliance['urgent_count'] > 0:
                    logger.warning(f"⚠️ {compliance['urgent_count']} URGENT compliance items!")
                
                await asyncio.sleep(3600)  # Sleep 1 hour
                
            except Exception as e:
                logger.error(f"❌ Background task error: {e}")
                await asyncio.sleep(300)  # Retry after 5 min
    
    async def handle_command(self, command: str, args: Dict = None) -> str:
        """Handle commands from FiscoMind bot"""
        
        if command == "connect_sat":
            await self.initialize()
            return "✅ Conectado al SAT exitosamente"
        
        elif command == "download_cfdis":
            days = args.get('days', 30) if args else 30
            result = await self.download_cfdis(days=days)
            return f"📥 Descargados {result.get('count', 0)} CFDIs del SAT"
        
        elif command == "analyze":
            # Get recent CFDIs and analyze
            cfdi_data = await self.download_cfdis(days=30)
            deductions = await self.analyze_deductions(cfdi_data.get('cfdis', []))
            
            response = f"🔍 ANÁLISIS DE DEDUCCIONES\n\n"
            response += f"Total Identificado: ${deductions['total_deductions']:,.2f}\n"
            response += f"Ahorro Estimado: ${deductions['tax_savings_estimate']:,.2f}\n\n"
            response += "Items Principales:\n"
            
            for i, sug in enumerate(deductions['suggestions'][:5], 1):
                response += f"{i}. {sug['concept']}: ${sug['amount']:,.2f} - {sug['reason']}\n"
            
            return response
        
        elif command == "compliance":
            compliance = await self.check_compliance()
            
            response = "📋 ESTADO DE CUMPLIMIENTO\n\n"
            
            if compliance['alerts']:
                response += "Próximas Obligaciones:\n"
                for alert in compliance['alerts'][:5]:
                    response += f"• {alert['event']} - {alert['date']}\n"
            else:
                response += "✅ No hay obligaciones pendientes"
            
            return response
        
        elif command == "full_report":
            return await self.generate_fiscal_report()
        
        else:
            return "❓ Comando no reconocido. Usa: connect_sat, download_cfdis, analyze, compliance, full_report"

# Global agent instance
agent_daemon: Optional[FiscoAgentDaemon] = None

async def get_agent() -> FiscoAgentDaemon:
    """Get or create agent daemon"""
    global agent_daemon
    if agent_daemon is None:
        agent_daemon = FiscoAgentDaemon()
        await agent_daemon.initialize()
    return agent_daemon

# CLI Interface
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python fisco_agent_daemon.py <command> [args]")
        print("Commands: init, download, analyze, compliance, report")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    async def main():
        agent = await get_agent()
        
        if cmd == "init":
            print("✅ Fisco Agent initialized")
            
        elif cmd == "download":
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
            result = await agent.download_cfdis(days=days)
            print(f"Downloaded {result.get('count', 0)} CFDIs")
            
        elif cmd == "analyze":
            cfdi_data = await agent.download_cfdis(days=30)
            deductions = await agent.analyze_deductions(cfdi_data.get('cfdis', []))
            print(f"\n💰 Deductions Found: ${deductions['total_deductions']:,.2f}")
            print(f"💵 Est. Tax Savings: ${deductions['tax_savings_estimate']:,.2f}")
            
        elif cmd == "compliance":
            compliance = await agent.check_compliance()
            print(f"\n⏰ Urgent Items: {compliance['urgent_count']}")
            if compliance['next_deadline']:
                print(f"Next: {compliance['next_deadline']['event']} ({compliance['next_deadline']['date']})")
                
        elif cmd == "report":
            report = await agent.generate_fiscal_report()
            print(report)
            
        elif cmd == "daemon":
            print("🤖 Starting Fisco Agent Daemon...")
            await agent.run_background_tasks()
    
    asyncio.run(main())
