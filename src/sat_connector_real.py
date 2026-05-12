#!/usr/bin/env python3
"""
SAT Connector Real v4 - Exact copy of working local version
Adapted for Railway (VAULT_DIR env var)
"""

import logging
import base64
import time
import zipfile
import io
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional

from satcfdi.models import Signer
from satcfdi.pacs.sat import SAT, TipoDescargaMasivaTerceros, EstadoComprobante

from secure_vault import Vault

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sat_connector_real")


class SATConnectorReal:
    """
    Cliente REAL de conexión al SAT usando satcfdi.
    Igual al que funciona en local.
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
    
    def submit_download_request(self, date_start: str, date_end: str, 
                                   tipo: str = "recibidos") -> Dict[str, Any]:
        """
        Submit CFDI download request to SAT (async).
        Uses METADATA + EstadoComprobante.TODOS (same as working local version).
        """
        if not self._is_connected:
            if not self.authenticate():
                raise ConnectionError("Could not connect to SAT")
        
        logger.info(f"📥 Submitting {tipo} request: {date_start} to {date_end}")
        
        start = date.fromisoformat(date_start)
        end = date.fromisoformat(date_end)
        
        try:
            # EXACT same call as working local version
            if tipo == "recibidos":
                result = self.sat.recover_comprobante_received_request(
                    fecha_inicial=start,
                    fecha_final=end,
                    rfc_receptor=self.rfc,
                    tipo_solicitud=TipoDescargaMasivaTerceros.METADATA,
                    estado_comprobante=EstadoComprobante.TODOS
                )
            else:
                # satcfdi uses "emitted" not "issued"
                result = self.sat.recover_comprobante_emitted_request(
                    fecha_inicial=start,
                    fecha_final=end,
                    rfc_emisor=self.rfc,
                    tipo_solicitud=TipoDescargaMasivaTerceros.METADATA,
                    estado_comprobante=EstadoComprobante.TODOS
                )
            
            request_id = result.get('IdSolicitud')
            cod_status = result.get('CodEstatus')
            mensaje = result.get('Mensaje', '')
            
            logger.info(f"📨 SAT Response: {cod_status} - {mensaje}")
            
            if request_id:
                self._pending_requests[request_id] = {
                    'id': request_id,
                    'submitted': datetime.now().isoformat(),
                    'date_start': date_start,
                    'date_end': date_end,
                    'tipo': tipo,
                }
                
                return {
                    "status": "submitted",
                    "id_solicitud": request_id,
                    "cod_status": cod_status,
                    "message": mensaje,
                    "tipo": tipo,
                    "date_range": f"{date_start} to {date_end}"
                }
            else:
                return {
                    "status": "error",
                    "cod_status": cod_status,
                    "message": mensaje
                }
            
        except Exception as e:
            logger.error(f"Submit download request failed: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}
    
    def check_request_status(self, id_solicitud: str) -> Dict[str, Any]:
        """Check status of a submitted request."""
        if not self._is_connected:
            if not self.authenticate():
                return {"status": "error", "message": "Not authenticated"}
        
        try:
            status = self.sat.recover_comprobante_status(id_solicitud)
            estado = status.get('EstadoSolicitud')
            num_cfdis = status.get('NumeroCFDIs', 0)
            
            logger.info(f"Status: {estado} | CFDIs: {num_cfdis} | Request: {id_solicitud}")
            
            if estado == self.STATUS_FINISHED:
                cfdis = self._process_packages(status)
                # Remove from pending
                if id_solicitud in self._pending_requests:
                    del self._pending_requests[id_solicitud]
                return {
                    "id_solicitud": id_solicitud,
                    "estado": estado,
                    "finished": True,
                    "num_cfdis": num_cfdis,
                    "cfdis": cfdis,
                    "cfdis_count": len(cfdis)
                }
            elif estado in [self.STATUS_ERROR, self.STATUS_REJECTED]:
                if id_solicitud in self._pending_requests:
                    del self._pending_requests[id_solicitud]
                return {
                    "id_solicitud": id_solicitud,
                    "estado": estado,
                    "finished": False,
                    "error": True,
                    "message": status.get('Mensaje', 'SAT error')
                }
            else:
                return {
                    "id_solicitud": id_solicitud,
                    "estado": estado,
                    "finished": False,
                    "num_cfdis": num_cfdis
                }
            
        except Exception as e:
            logger.error(f"Check status failed: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}
    
    def _process_packages(self, status: Dict) -> List[Dict]:
        """Download and parse CFDI packages (same as working local version)"""
        paquetes = status.get('IdsPaquetes') or []
        cfdis = []
        
        for pkg_id in paquetes:
            try:
                # Local version: sat.recover_comprobante_download returns (msg, content)
                result = self.sat.recover_comprobante_download(pkg_id)
                
                # Handle both tuple and single return
                if isinstance(result, tuple):
                    msg, content = result
                else:
                    content = result
                
                if content and len(str(content)) > 100:
                    cfdis.extend(self._parse_package(content))
                    
            except Exception as e:
                logger.error(f"Error downloading package {pkg_id}: {e}")
        
        logger.info(f"✅ Extracted {len(cfdis)} CFDIs from {len(paquetes)} packages")
        return cfdis
    
    def _parse_package(self, b64_content: str) -> List[Dict]:
        """Parse ZIP package containing CFDI metadata (CSV format from METADATA request)"""
        cfdis = []
        try:
            decoded = base64.b64decode(b64_content)
            with zipfile.ZipFile(io.BytesIO(decoded)) as zf:
                for fname in zf.namelist():
                    if fname.endswith('.txt'):
                        content = zf.read(fname).decode('utf-8')
                        lines = content.strip().split('\n')
                        
                        for line in lines[1:]:  # Skip header
                            parts = line.split('~')
                            if len(parts) >= 11:
                                cfdis.append({
                                    'uuid': parts[0],
                                    'rfc_emisor': parts[1],
                                    'nombre_emisor': parts[2],
                                    'rfc_receptor': parts[3],
                                    'nombre_receptor': parts[4],
                                    'pac': parts[5],
                                    'fecha_emision': parts[6][:10] if parts[6] else '',
                                    'fecha_certificacion': parts[7],
                                    'monto': float(parts[8]) if parts[8] else 0,
                                    'efecto': parts[9],  # I/E/P/N
                                    'estatus': parts[10],  # 1=Vigente, 0=Cancelado
                                    'fecha_cancelacion': parts[11] if len(parts) > 11 else '',
                                    'deductible': self._is_deductible(parts[1], parts[2])
                                })
        except Exception as e:
            logger.error(f"Parse package error: {e}")
        return cfdis
    
    def _is_deductible(self, rfc: str, nombre: str) -> bool:
        """Check if expense is potentially deductible"""
        keywords = [
            'gasolina', 'telmex', 'izzi', 'totalplay', 'uber', 'didi',
            'amazon', 'microsoft', 'google', 'apple', 'stripe', 'github',
            'aws', 'azure', 'cloud', 'oficina', 'papeleria', 'software',
            'restaurante', 'comida', 'transporte', 'seguro', 'hospital',
            'farmacia', 'doctor', 'medico', 'renta', 'internet', 'servicio'
        ]
        search = f"{nombre} {rfc}".lower()
        return any(kw in search for kw in keywords)
    
    def download_cfdis(self, date_start: str, date_end: str, 
                       tipo: str = "recibidos") -> List[Dict[str, Any]]:
        """
        Blocking download - submits request and polls until done.
        WARNING: Can take 30-120s. Use submit_download_request for async.
        """
        result = self.submit_download_request(date_start, date_end, tipo)
        
        if result.get('status') != 'submitted':
            return []
        
        id_solicitud = result['id_solicitud']
        logger.info(f"⏳ Polling SAT for request {id_solicitud}...")
        
        max_wait = 120
        interval = 5
        elapsed = 0
        
        while elapsed < max_wait:
            time.sleep(interval)
            elapsed += interval
            
            status = self.check_request_status(id_solicitud)
            
            if status.get('finished'):
                return status.get('cfdis', [])
            elif status.get('error'):
                return []
        
        logger.warning(f"Timeout waiting for {id_solicitud}")
        return []


if __name__ == "__main__":
    print("🚀 Testing SAT Real Connection v4...")
    connector = SATConnectorReal(rfc="MUTM8610091NA")
    
    if connector.authenticate():
        print("✅ Auth OK")
        result = connector.submit_download_request("2026-04-01", "2026-04-30", "recibidos")
        print(f"📤 Submit: {result}")
    else:
        print("❌ Auth failed")