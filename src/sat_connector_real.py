#!/usr/bin/env python3
"""
SAT Connector Real v3 - Conexión auténtica al SAT usando satcfdi
Descarga CFDIs reales usando FIEL (e.firma) del vault encriptado
"""

import logging
import time
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional

from satcfdi.models import Signer
from satcfdi.pacs.sat import SAT, TipoDescargaMasivaTerceros

from secure_vault import Vault

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sat_connector_real")


def to_dict(obj):
    """Convert satcfdi response to dict"""
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, '__dict__'):
        return obj.__dict__
    if hasattr(obj, 'to_dict'):
        return obj.to_dict()
    # Fallback: try to parse as dict-like
    try:
        return dict(obj)
    except:
        return {}


class SATConnectorReal:
    """
    Cliente REAL de conexión al SAT usando satcfdi.
    Autenticación FIEL, descarga masiva de CFDIs, consulta de estado.
    """
    
    STATUS_ACCEPTED = 1
    STATUS_IN_PROGRESS = 2
    STATUS_FINISHED = 3
    STATUS_ERROR = 4
    STATUS_REJECTED = 5
    
    def __init__(self, rfc: str = "MUTM8610091NA"):
        self.rfc = rfc
        self.vault = Vault()
        self.signer: Optional[Signer] = None
        self.sat: Optional[SAT] = None
        self._is_connected = False
        self._pending_requests: Dict[str, Dict] = {}
        
    def authenticate(self) -> bool:
        """Authenticate with SAT using FIEL from encrypted vault"""
        logger.info(f"🔐 Authenticating with SAT for RFC: {self.rfc}")
        
        try:
            password = self.vault.get_password('fiel_sat')
            key_data = self.vault.decrypt_to_memory('fiel_key')
            cer_data = self.vault.decrypt_to_memory('fiel_cer')
            
            self.signer = Signer.load(
                certificate=cer_data,
                key=key_data,
                password=password.encode()
            )
            
            self.sat = SAT(self.signer)
            self._is_connected = True
            
            logger.info(f"✅ SAT Authentication successful. RFC: {self.signer.rfc}")
            return True
            
        except Exception as e:
            logger.error(f"❌ SAT Authentication failed: {e}")
            self._is_connected = False
            return False
    
    def download_cfdis(self, date_start: str, date_end: str, 
                       tipo: str = "recibidos",
                       include_xml: bool = True) -> List[Dict[str, Any]]:
        """
        Download CFDIs from SAT portal using descarga masiva.
        """
        if not self._is_connected:
            if not self.authenticate():
                raise ConnectionError("Could not connect to SAT")
        
        logger.info(f"📥 Requesting CFDIs {tipo} from {date_start} to {date_end}")
        
        start = date.fromisoformat(date_start)
        end = date.fromisoformat(date_end)
        request_type = TipoDescargaMasivaTerceros.CFDI if include_xml else TipoDescargaMasivaTerceros.METADATA
        
        try:
            # Submit request - simpler, without estado_comprobante
            if tipo == "recibidos":
                result = self.sat.recover_comprobante_received_request(
                    fecha_inicial=start,
                    fecha_final=end,
                    rfc_receptor=self.rfc,
                    tipo_solicitud=request_type
                )
            else:
                result = self.sat.recover_comprobante_emitted_request(
                    fecha_inicial=start,
                    fecha_final=end,
                    rfc_emisor=self.rfc,
                    tipo_solicitud=request_type
                )
            
            result_dict = to_dict(result)
            cod_status = result_dict.get('CodEstatus', result_dict.get('cod_estatus'))
            mensaje = result_dict.get('Mensaje', result_dict.get('mensaje', ''))
            id_solicitud = result_dict.get('IdSolicitud', result_dict.get('id_solicitud'))
            
            logger.info(f"📨 Request result: {cod_status} - {mensaje}")
            
            if not id_solicitud:
                if cod_status in ['5004', 5004] or 'no encontrad' in str(mensaje).lower():
                    logger.info("No CFDIs found for this period")
                    return []
                logger.warning(f"No request ID. Code: {cod_status}, Message: {mensaje}")
                return []
            
            # Poll for completion
            logger.info(f"⏳ Waiting for SAT to process request {id_solicitud}...")
            
            max_wait = 60
            interval = 5
            elapsed = 0
            
            while elapsed < max_wait:
                time.sleep(interval)
                elapsed += interval
                
                status = self.sat.recover_comprobante_status(id_solicitud)
                status_dict = to_dict(status)
                
                estado = status_dict.get('EstadoSolicitud', status_dict.get('estado_solicitud'))
                num_cfdis = status_dict.get('NumeroCFDIs', status_dict.get('numero_cfdis', 0))
                
                logger.info(f"  Status: {estado} | CFDIs: {num_cfdis} | Elapsed: {elapsed}s")
                
                if estado == self.STATUS_FINISHED:
                    return self._download_packages(status_dict)
                elif estado == self.STATUS_REJECTED:
                    logger.error(f"SAT rejected request: {status_dict.get('Mensaje')}")
                    return []
                elif estado == self.STATUS_ERROR:
                    logger.error(f"SAT error: {status_dict.get('Mensaje')}")
                    return []
                elif estado == self.STATUS_ACCEPTED:
                    continue
            
            # Timeout - store for later
            logger.warning(f"Timeout after {max_wait}s. Storing request {id_solicitud}.")
            self._pending_requests[id_solicitud] = {
                'id': id_solicitud,
                'submitted': datetime.now().isoformat(),
                'date_start': date_start,
                'date_end': date_end,
                'tipo': tipo
            }
            return []
            
        except Exception as e:
            logger.error(f"❌ CFDI download failed: {e}", exc_info=True)
            return []
    
    def _download_packages(self, status: Dict) -> List[Dict[str, Any]]:
        """Download and parse CFDI packages"""
        id_paquetes = status.get('IdsPaquetes') or status.get('IdPaquetes') or status.get('ids_paquetes') or []
        num_cfdis = status.get('NumeroCFDIs', 0)
        
        logger.info(f"📦 Downloading {len(id_paquetes)} packages ({num_cfdis} CFDIs)")
        
        all_cfdis = []
        
        for pkg_id in id_paquetes:
            try:
                result = self.sat.recover_comprobante_download(pkg_id)
                result_dict = to_dict(result)
                
                logger.info(f"  Package {pkg_id}: downloaded")
                
                if isinstance(result_dict, dict):
                    for uuid_key, cfdi_xml in result_dict.items():
                        cfdi_info = self._extract_cfdi_info(cfdi_xml, uuid_key)
                        if cfdi_info:
                            all_cfdis.append(cfdi_info)
                            
            except Exception as e:
                logger.error(f"Error downloading package {pkg_id}: {e}")
        
        logger.info(f"✅ Extracted {len(all_cfdis)} CFDIs")
        return all_cfdis
    
    def _extract_cfdi_info(self, xml_content: bytes, uuid: str = None) -> Optional[Dict[str, Any]]:
        """Extract key info from CFDI XML"""
        from xml.etree import ElementTree as ET
        try:
            if isinstance(xml_content, str):
                root = ET.fromstring(xml_content)
            else:
                root = ET.fromstring(xml_content)
            
            ns = {'cfdi': 'http://www.sat.gob.mx/cfd/4', 
                  'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital'}
            
            emisor = root.find('.//cfdi:Emisor', ns)
            receptor = root.find('.//cfdi:Receptor', ns)
            timbre = root.find('.//tfd:TimbreFiscalDigital', ns)
            
            emisor_nombre = emisor.get('Nombre', 'Unknown') if emisor is not None else 'Unknown'
            emisor_rfc = emisor.get('Rfc', 'Unknown') if emisor is not None else 'Unknown'
            
            total = float(root.get('Total', 0))
            subtotal = float(root.get('SubTotal', 0))
            fecha = root.get('Fecha', '')
            folio = root.get('Folio', 'S/N')
            tipo_comp = root.get('TipoDeComprobante', 'I')
            
            if not uuid and timbre is not None:
                uuid = timbre.get('UUID', '')
            
            return {
                'uuid': uuid or '',
                'folio': folio,
                'emisor': emisor_nombre,
                'emisor_rfc': emisor_rfc,
                'receptor_rfc': receptor.get('Rfc', '') if receptor is not None else '',
                'monto': total,
                'subtotal': subtotal,
                'fecha': fecha[:10] if fecha else '',
                'tipo_comprobante': tipo_comp,
                'status': 'Vigente',
                'deductible': self._is_deductible(emisor_rfc, emisor_nombre)
            }
        except Exception as e:
            logger.error(f"Error extracting CFDI info: {e}")
            return None
    
    def _is_deductible(self, emisor_rfc: str, emisor_nombre: str) -> bool:
        """Check if expense is potentially deductible"""
        deductible_keywords = [
            'gasolina', 'telmex', 'izzi', 'totalplay', 'uber', 'didi',
            'amazon', 'microsoft', 'google', 'apple', 'stripe', 'github',
            'aws', 'azure', 'cloud', 'oficina', 'papeleria', 'software',
            'restaurante', 'comida', 'transporte', 'seguro', 'hospital',
            'farmacia', 'doctor', 'medico', 'renta', 'internet', 'servicio'
        ]
        search_text = f"{emisor_nombre} {emisor_rfc}".lower()
        return any(kw in search_text for kw in deductible_keywords)
    
    def get_compliance_opinion(self) -> Dict[str, Any]:
        """Get compliance opinion from SAT"""
        if not self._is_connected:
            if not self.authenticate():
                return {
                    "rfc": self.rfc, "status": "Error",
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "pending_obligations": 0, "verified": False
                }
        
        try:
            pending = self.sat.pending(self.rfc)
            pending_dict = to_dict(pending) if not isinstance(pending, dict) else pending
            
            return {
                "rfc": self.rfc,
                "status": "Positiva" if not pending_dict else "Con pendientes",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "pending_obligations": len(pending_dict) if isinstance(pending_dict, (dict, list)) else 0,
                "verified": True
            }
        except Exception as e:
            logger.error(f"Compliance check failed: {e}")
            return {
                "rfc": self.rfc, "status": "Error",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "pending_obligations": 0, "verified": False
            }


# Test
if __name__ == "__main__":
    print("🚀 Testing SAT Real Connection v3...")
    
    connector = SATConnectorReal(rfc="MUTM8610091NA")
    
    if connector.authenticate():
        print("✅ Auth OK")
        
        # Test CFDI download
        print("\n📥 Downloading CFDIs...")
        cfdis = connector.download_cfdis(
            date_start="2026-01-01",
            date_end="2026-01-31",
            tipo="recibidos"
        )
        
        print(f"\n📊 Result: {len(cfdis)} CFDIs")
        for cfdi in cfdis[:5]:
            print(f"  • {cfdi['emisor']} | ${cfdi['monto']:,.2f} | {cfdi['fecha']} | Deductible: {cfdi['deductible']}")
        
        # Test compliance
        print("\n📋 Compliance:")
        opinion = connector.get_compliance_opinion()
        print(f"  Status: {opinion['status']} | Pending: {opinion['pending_obligations']}")
    else:
        print("❌ Auth failed")