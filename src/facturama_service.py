#!/usr/bin/env python3
"""
Facturama PAC Integration Service
Handles real CFDI emission, cancellation, and complementos de pago
"""

import os
import logging
import requests
from typing import Dict, Any, Optional
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("facturama_service")


class FacturamaService:
    """
    Facturama PAC API Integration
    Docs: https://apisandbox.facturama.mx/Docs
    """
    
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        self.api_key = api_key or os.environ.get('FACTURAMA_API_KEY')
        self.api_secret = api_secret or os.environ.get('FACTURAMA_API_SECRET')
        
        # Base URLs
        self.sandbox_url = "https://apisandbox.facturama.mx"
        self.production_url = "https://api.facturama.mx"
        
        # Use sandbox for development
        self.base_url = self.sandbox_url if os.environ.get('FACTURAMA_SANDBOX', 'true').lower() == 'true' else self.production_url
        
        self.session = requests.Session()
        self.session.auth = (self.api_key, self.api_secret)
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
                    "message": error_data.get('Message', str(e)),
                    "details": error_data
                }
            except:
                return {
                    "status": "error",
                    "message": str(e),
                    "http_status": e.response.status_code
                }
        except Exception as e:
            logger.error(f"Request error: {e}")
            return {"status": "error", "message": str(e)}
    
    def emit_cfdi(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Emit a CFDI 4.0 invoice
        
        Required fields:
        - Receiver: {Name, Rfc, CfdiUse, FiscalRegime, TaxZipCode}
        - Issuer: (optional, uses account default)
        - Items: [{ProductCode, Description, UnitCode, UnitPrice, Quantity, Subtotal}]
        - PaymentForm
        - PaymentMethod
        
        Returns:
        - OriginalString
        - CfdiSign
        - CadenaOriginalSAT
        - TimbreFiscalDigital
        - QRCode
        - Status: 1 (active)
        - StatusCode: "1"
        """
        logger.info(f"Emitting CFDI for receiver: {invoice_data.get('Receiver', {}).get('Name', 'N/A')}")
        
        # Ensure required structure
        if 'Receiver' not in invoice_data:
            return {"status": "error", "message": "Receiver data required"}
        
        if 'Items' not in invoice_data or not invoice_data['Items']:
            return {"status": "error", "message": "Items (conceptos) required"}
        
        result = self._make_request('POST', '/2/cfdis', invoice_data)
        
        if result.get('status') != 'error':
            logger.info(f"CFDI emitted successfully: {result.get('Id', 'N/A')}")
            
        return result
    
    def cancel_cfdi(self, cfdi_id: str, reason: str = "02") -> Dict[str, Any]:
        """
        Cancel a CFDI
        
        Args:
            cfdi_id: The CFDI ID from Facturama
            reason: Cancellation reason code:
                - 01: Comprobantes emitidos con errores con relación
                - 02: Comprobantes emitidos con errores sin relación
                - 03: No se llevó a cabo la operación
                - 04: Operación nominativa relacionada en la factura global
        """
        logger.info(f"Cancelling CFDI: {cfdi_id}")
        
        cancel_data = {
            "Motivo": reason,
            "FolioSustitucion": ""  # Required if reason is 01
        }
        
        result = self._make_request('DELETE', f'/2/cfdis/{cfdi_id}', cancel_data)
        return result
    
    def get_cfdi(self, cfdi_id: str) -> Dict[str, Any]:
        """Get CFDI details including PDF/XML download URLs"""
        return self._make_request('GET', f'/cfdi/{cfdi_id}')
    
    def download_xml(self, cfdi_id: str) -> bytes:
        """Download CFDI XML file"""
        url = f"{self.base_url}/cfdi/xml/{cfdi_id}"
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        return response.content
    
    def download_pdf(self, cfdi_id: str) -> bytes:
        """Download CFDI PDF file"""
        url = f"{self.base_url}/Cfdi/pdf/{cfdi_id}"
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        return response.content
    
    def emit_complemento_pago(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Emit Complemento de Pago (type P CFDI)
        
        Required fields:
        - Receiver: {Name, Rfc, CfdiUse="CP01", FiscalRegime, TaxZipCode}
        - PaymentForm
        - RelatedDocuments: [{
            "Uuid": "...",
            "PaymentMethod": "...",
            "PartialityNumber": 1,
            "PreviousAmount": ...,
            "AmountPaid": ...,
            "OutstandingBalance": ...
        }]
        """
        logger.info("Emitting Complemento de Pago")
        
        # Ensure it's marked as payment type
        payment_data['CfdiType'] = 'P'
        
        return self._make_request('POST', '/2/cfdis', payment_data)
    
    def list_cfdis(self, rfcs: Optional[list] = None) -> list:
        """List emitted CFDIs"""
        endpoint = '/cfdi'
        if rfcs:
            rfc_param = ','.join(rfcs)
            endpoint = f'/cfdi?rfc={rfc_param}'
        
        result = self._make_request('GET', endpoint)
        if isinstance(result, list):
            return result
        return []


# Test function
def test_connection():
    """Test Facturama connection"""
    service = FacturamaService()
    
    # Try to list CFDIs (should work even with empty list)
    try:
        response = requests.get(
            f"{service.base_url}/2/cfdis",
            auth=(service.api_key, service.api_secret),
            timeout=10
        )
        if response.status_code == 200:
            print("✅ Facturama connection successful")
            return True
        else:
            print(f"❌ Connection failed: {response.status_code}")
            print(response.text)
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False


if __name__ == "__main__":
    test_connection()
