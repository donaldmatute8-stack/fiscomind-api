#!/usr/bin/env python3
"""
Facturama PAC Integration Service - REAL CFDI Emission
Updated based on official docs: https://apisandbox.facturama.mx/Docs

Authentication: Basic Auth (username/password)
Sandbox: https://apisandbox.facturama.mx
Production: https://api.facturama.mx
"""

import os
import logging
import requests
import base64
from typing import Dict, Any, Optional
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("facturama_service")


class FacturamaService:
    """
    Facturama PAC API Integration - Real CFDI Emission
    """
    
    def __init__(self, username: Optional[str] = None, password: Optional[str] = None):
        self.username = username or os.environ.get('FACTURAMA_USERNAME')
        self.password = password or os.environ.get('FACTURAMA_PASSWORD')
        
        # Determine environment
        self.is_sandbox = os.environ.get('FACTURAMA_SANDBOX', 'true').lower() == 'true'
        
        # Base URLs
        self.base_url = "https://apisandbox.facturama.mx" if self.is_sandbox else "https://api.facturama.mx"
        
        # Create session with Basic Auth
        self.session = requests.Session()
        if self.username and self.password:
            self.session.auth = (self.username, self.password)
        
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make authenticated request to Facturama API"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method.upper() == 'GET':
                response = self.session.get(url, timeout=30)
            elif method.upper() == 'POST':
                response = self.session.post(url, json=data, timeout=30)
            elif method.upper() == 'PUT':
                response = self.session.put(url, json=data, timeout=30)
            elif method.upper() == 'DELETE':
                response = self.session.delete(url, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            
            if response.status_code == 204:
                return {"status": "success"}
            
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP Error: {e.response.status_code} - {e.response.text}")
            try:
                error_data = e.response.json()
                return {
                    "status": "error",
                    "message": error_data.get('Message', error_data.get('message', str(e))),
                    "details": error_data
                }
            except:
                return {
                    "status": "error",
                    "message": str(e),
                    "http_status": e.response.status_code,
                    "response_text": e.response.text
                }
        except Exception as e:
            logger.error(f"Request error: {e}")
            return {"status": "error", "message": str(e)}
    
    def test_connection(self) -> bool:
        """Test connection to Facturama API"""
        try:
            # Try to get account info
            result = self._make_request('GET', '/api/Account/UserInfo')
            if result.get('status') != 'error':
                logger.info("✅ Facturama connection successful")
                return True
            else:
                logger.error(f"❌ Connection failed: {result.get('message')}")
                return False
        except Exception as e:
            logger.error(f"❌ Connection error: {e}")
            return False
    
    def emit_cfdi(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Emit a REAL CFDI 4.0 invoice via Facturama
        
        Required fields in invoice_data:
        {
            "Receiver": {
                "Name": "...",
                "Rfc": "...",
                "CfdiUse": "G03",
                "FiscalRegime": "601",
                "TaxZipCode": "64000"
            },
            "Items": [
                {
                    "ProductCode": "84111506",
                    "Description": "...",
                    "UnitCode": "E48",
                    "UnitPrice": 100.00,
                    "Quantity": 1,
                    "TaxObject": "02"
                }
            ],
            "PaymentForm": "03",
            "PaymentMethod": "PUE",  // or "PPD"
            "ExpeditionPlace": "64000"
        }
        """
        logger.info(f"Emitting CFDI to: {invoice_data.get('Receiver', {}).get('Name', 'N/A')}")
        
        # Use Facturama v2 API endpoint
        result = self._make_request('POST', '/2/cfdis', invoice_data)
        
        if result.get('status') == 'error':
            logger.error(f"Emission failed: {result.get('message')}")
            return result
        
        # Success - extract relevant data
        logger.info(f"✅ CFDI emitted: {result.get('Id')}")
        return {
            "status": "success",
            "message": "CFDI emitido correctamente",
            "cfdi": {
                "id": result.get('Id'),
                "uuid": result.get('Complement', {}).get('TaxStamp', {}).get('Uuid'),
                "cfdi_type": result.get('CfdiType'),
                "total": result.get('Total'),
                "subtotal": result.get('Subtotal'),
                "taxes": result.get('Taxes'),
                "currency": result.get('Currency'),
                "exchange_rate": result.get('ExchangeRate'),
                "date": result.get('Date'),
                "status": result.get('Status'),
                "original_string": result.get('OriginalString'),
                "cfdi_sign": result.get('CfdiSign'),
                "sat_seal": result.get('Complement', {}).get('TaxStamp', {}).get('SatSeal'),
                "qr_code": result.get('Complement', {}).get('TaxStamp', {}).get('QrCode'),
                "pdf_url": f"/facturama/download/{result.get('Id')}/pdf",
                "xml_url": f"/facturama/download/{result.get('Id')}/xml"
            }
        }
    
    def cancel_cfdi(self, cfdi_id: str, reason: str = "02", uuid_replacement: str = "") -> Dict[str, Any]:
        """
        Cancel a CFDI
        
        Args:
            cfdi_id: Facturama CFDI ID
            reason: Cancellation reason:
                - 01: Comprobantes emitidos con errores con relación
                - 02: Comprobantes emitidos con errores sin relación
                - 03: No se llevó a cabo la operación
                - 04: Operación nominativa relacionada en la factura global
            uuid_replacement: Required if reason is 01
        """
        logger.info(f"Cancelling CFDI: {cfdi_id}, reason: {reason}")
        
        endpoint = f"/cfdi/{cfdi_id}?motive={reason}"
        if reason == "01" and uuid_replacement:
            endpoint += f"&uuidReplacement={uuid_replacement}"
        
        result = self._make_request('DELETE', endpoint)
        
        if result.get('status') == 'error':
            return result
        
        return {
            "status": "success",
            "message": "CFDI cancelado correctamente",
            "cancelled_cfdi_id": cfdi_id,
            "acknowledgment": result.get('Acuse')
        }
    
    def get_cfdi_detail(self, cfdi_id: str, cfdi_type: str = "issued") -> Dict[str, Any]:
        """Get CFDI details"""
        return self._make_request('GET', f'/Cfdi/{cfdi_id}?type={cfdi_type}')
    
    def download_xml(self, cfdi_id: str, cfdi_type: str = "issued") -> bytes:
        """Download CFDI XML file"""
        url = f"{self.base_url}/Cfdi/xml/{cfdi_type}/{cfdi_id}"
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        return response.content
    
    def download_pdf(self, cfdi_id: str, cfdi_type: str = "issued") -> bytes:
        """Download CFDI PDF file"""
        url = f"{self.base_url}/Cfdi/pdf/{cfdi_type}/{cfdi_id}"
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        return response.content
    
    def list_cfdis(self, keyword: str = "", cfdi_type: str = "issued", status: str = "all", page: int = 1) -> Dict[str, Any]:
        """List CFDIs with optional filters"""
        endpoint = f"/cfdi?type={cfdi_type}&keyword={keyword}&status={status}&page={page}"
        return self._make_request('GET', endpoint)
    
    def send_cfdi_email(self, cfdi_id: str, email: str, subject: str = "", comments: str = "", cfdi_type: str = "issued") -> Dict[str, Any]:
        """Send CFDI by email"""
        endpoint = f"/Cfdi?cfdiType={cfdi_type}&cfdiId={cfdi_id}&email={email}"
        if subject:
            endpoint += f"&subject={subject}"
        if comments:
            endpoint += f"&comments={comments}"
        
        return self._make_request('POST', endpoint)
    
    def get_account_info(self) -> Dict[str, Any]:
        """Get account information"""
        return self._make_request('GET', '/api/Account/UserInfo')


# Helper function
def create_facturama_service() -> FacturamaService:
    """Factory function to create Facturama service with environment variables"""
    return FacturamaService()


if __name__ == "__main__":
    # Test connection
    service = FacturamaService()
    is_connected = service.test_connection()
    
    if is_connected:
        print("✅ Facturama service is ready")
        # Get account info
        info = service.get_account_info()
        print(f"Account: {info.get('Name', 'N/A')}")
    else:
        print("❌ Failed to connect to Facturama")
        print("Make sure to set FACTURAMA_USERNAME and FACTURAMA_PASSWORD")
