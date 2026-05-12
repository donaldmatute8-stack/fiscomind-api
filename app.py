#!/usr/bin/env python3
"""
FiscoMind Railway API v4.0 - CONEXIÓN REAL AL SAT
- Sincronización CFDIs reales via satcfdi
- Emisión facturas CFDI 4.0 via portal gratuito SAT
- Cancelación real
- Dashboard con datos reales
- Vault encriptado para credenciales
"""
import os
import sys
import json
import base64
import io
import time
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from xml.etree import ElementTree as ET

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

app = Flask(__name__)
CORS(app, origins=["*"], supports_credentials=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fiscomind-api")

# Data directory (persistente en Railway)
DATA_DIR = Path(os.environ.get('DATA_DIR', '/tmp/fiscomind-data'))
DATA_DIR.mkdir(exist_ok=True, parents=True)

# CFDI cache file
CACHE_FILE = DATA_DIR / 'cfdi_cache.json'

MONTH_NAMES = {
    '01': 'Enero', '02': 'Febrero', '03': 'Marzo', '04': 'Abril',
    '05': 'Mayo', '06': 'Junio', '07': 'Julio', '08': 'Agosto',
    '09': 'Septiembre', '10': 'Octubre', '11': 'Noviembre', '12': 'Diciembre'
}

# ─── Vault & SAT Connector ──────────────────────────────────────────

def get_vault():
    """Get vault instance with credentials"""
    from secure_vault import Vault
    return Vault()

def get_sat_connector():
    """Get or create SAT connector with real FIEL auth"""
    try:
        from sat_connector_real import SATConnectorReal
        connector = SATConnectorReal(rfc="MUTM8610091NA")
        return connector
    except Exception as e:
        logger.error(f"Error creating SAT connector: {e}")
        return None

# Global connector (lazy init)
_sat_connector = None

def sat_connector():
    global _sat_connector
    if _sat_connector is None:
        _sat_connector = get_sat_connector()
    return _sat_connector

# ─── CFDI Cache ─────────────────────────────────────────────────────

def load_cache() -> Dict:
    """Load CFDI cache from disk"""
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"last_sync": None, "recibidos": [], "emitidos": []}

def save_cache(data: Dict):
    """Save CFDI cache to disk"""
    with open(CACHE_FILE, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

# ─── ROUTES ─────────────────────────────────────────────────────────

@app.route('/')
def index():
    sat_status = "connected" if sat_connector() and sat_connector()._is_connected else "available"
    return jsonify({
        "name": "FiscoMind API",
        "version": "4.0.0",
        "status": "running",
        "sat_connection": sat_status,
        "mode": "REAL",
        "endpoints": {
            "GET /": "Info",
            "GET /health": "Health check",
            "GET /dashboard": "Dashboard fiscal (datos reales)",
            "POST /sync": "Sincronizar CFDIs con SAT real",
            "GET /sync/status": "Estado de sincronización pendiente",
            "GET /cfdis": "Lista CFDIs (cache + reales)",
            "GET /cfdis/<uuid>": "Detalle CFDI",
            "GET /emitidos": "Facturas emitidas",
            "POST /emitir": "Emitir factura CFDI 4.0 (SAT gratuito)",
            "POST /cancelar": "Cancelar factura (SAT real)",
            "GET /obligaciones": "Obligaciones fiscales",
            "GET /opinion": "Opinión de cumplimiento SAT",
        }
    })

@app.route('/health')
def health():
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat(), "mode": "REAL"})

@app.route('/dashboard')
def dashboard():
    cache = load_cache()
    recibidos = cache.get('recibidos', [])
    emitidos = cache.get('emitidos', [])
    
    total_ingresos = sum(float(c.get('monto', 0)) for c in recibidos if c.get('tipo_comprobante') == 'I')
    total_egresos = sum(float(c.get('monto', 0)) for c in recibidos if c.get('tipo_comprobante') == 'E')
    total_emitidos = sum(float(c.get('monto', 0)) for c in emitidos)
    
    # Calcular deducibles
    deducibles = [c for c in recibidos if c.get('deductible')]
    total_deducible = sum(float(c.get('monto', 0)) for c in deducibles)
    
    return jsonify({
        "rfc": "MUTM8610091NA",
        "last_sync": cache.get('last_sync'),
        "summary": {
            "total_recibidos": len(recibidos),
            "total_emitidos": len(emitidos),
            "total_ingresos": round(total_ingresos, 2),
            "total_egresos": round(total_egresos, 2),
            "total_emitido_monto": round(total_emitidos, 2),
            "total_deducible": round(total_deducible, 2),
            "ahorro_isr_estimado": round(total_deducible * 0.30, 2),
            "deducibles_count": len(deducibles)
        },
        "recent_cfdis": (recibidos + emitidos)[:20]
    })

@app.route('/sync', methods=['POST'])
def sync():
    """Sincronizar CFDIs con SAT real usando FIEL del vault"""
    connector = sat_connector()
    if not connector:
        return jsonify({"status": "error", "message": "SAT connector no disponible"}), 500
    
    data = request.json or {}
    date_start = data.get('date_start', (date.today() - timedelta(days=90)).isoformat())
    date_end = data.get('date_end', date.today().isoformat())
    
    try:
        if not connector._is_connected:
            auth_ok = connector.authenticate()
            if not auth_ok:
                return jsonify({"status": "error", "message": "Autenticación FIEL fallida. Verifica credenciales del vault."}), 401
        
        wait = data.get('wait', True)  # By default, long-poll until SAT finishes
        
        # Download recibidos (long-poll by default)
        logger.info(f"📥 Syncing recibidos: {date_start} to {date_end}")
        recibidos = connector.download_cfdis(date_start, date_end, tipo="recibidos")
        
        # Download emitidos
        logger.info(f"📤 Syncing emitidos: {date_start} to {date_end}")
        emitidos = connector.download_cfdis(date_start, date_end, tipo="emitidos")
        
        # Save pending requests for later checking
        pending = dict(connector._pending_requests)
        
        # Update cache
        cache = load_cache()
        cache['last_sync'] = datetime.now().isoformat()
        cache['last_date_start'] = date_start
        cache['last_date_end'] = date_end
        if recibidos:
            cache['recibidos'] = recibidos
        if emitidos:
            cache['emitidos'] = emitidos
        save_cache(cache)
        
        total_r = len(recibidos)
        total_e = len(emitidos)
        
        if total_r > 0 or total_e > 0:
            msg = f"Sincronización completada: {total_r} recibidos, {total_e} emitidos"
            status = "success"
        elif pending:
            msg = f"SAT procesando solicitud. {len(pending)} pendientes. Consulta GET /sync/status"
            status = "pending"
            # Store pending request IDs for later polling
            cache['pending_requests'] = {k: v for k, v in pending.items()}
            save_cache(cache)
        else:
            msg = f"Sincronización completada sin CFDIs nuevos para el período"
            status = "success"
        
        return jsonify({
            "status": status,
            "message": msg,
            "date_range": f"{date_start} to {date_end}",
            "recibidos_count": total_r,
            "emitidos_count": total_e,
            "pending_requests": len(pending),
            "last_sync": cache['last_sync']
        })
        
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/sync/status')
def sync_status():
    """Check pending SAT requests and try to download if ready"""
    connector = sat_connector()
    cache = load_cache()
    
    pending_ids = cache.get('pending_requests', {})
    newly_downloaded = []
    
    # Try to check/download any pending requests
    if connector and pending_ids:
        try:
            if not connector._is_connected:
                connector.authenticate()
            
            for req_id in list(pending_ids.keys()):
                try:
                    status = connector.sat.recover_comprobante_status(req_id)
                    estado = status.get('EstadoSolicitud')
                    
                    if estado == 3:  # FINISHED
                        cfdis = connector._download_packages(status)
                        newly_downloaded.extend(cfdis)
                        del pending_ids[req_id]
                        logger.info(f"✅ Downloaded {len(cfdis)} CFDIs from pending request {req_id}")
                    elif estado in [4, 5]:  # ERROR or REJECTED
                        del pending_ids[req_id]
                        logger.warning(f"Request {req_id} finished with state {estado}")
                except Exception as e:
                    logger.error(f"Error checking request {req_id}: {e}")
        except Exception as e:
            logger.error(f"Auth error in sync/status: {e}")
    
    # Update cache with new CFDIs
    if newly_downloaded:
        cache['recibidos'].extend(newly_downloaded)
        cache['pending_requests'] = pending_ids
        cache['last_sync'] = datetime.now().isoformat()
        save_cache(cache)
    
    return jsonify({
        "connected": connector._is_connected if connector else False,
        "last_sync": cache.get('last_sync'),
        "pending_requests": len(pending_ids),
        "newly_downloaded": len(newly_downloaded),
        "cache_recibidos": len(cache.get('recibidos', [])),
        "cache_emitidos": len(cache.get('emitidos', []))
    })

@app.route('/cfdis')
def list_cfdis():
    cache = load_cache()
    tipo = request.args.get('tipo', 'all')
    
    cfdis = []
    if tipo in ['all', 'recibidos']:
        cfdis.extend(cache.get('recibidos', []))
    if tipo in ['all', 'emitidos']:
        cfdis.extend(cache.get('emitidos', []))
    
    return jsonify({
        "rfc": "MUTM8610091NA",
        "tipo": tipo,
        "total": len(cfdis),
        "cfdis": cfdis,
        "last_sync": cache.get('last_sync')
    })

@app.route('/cfdis/<uuid>')
def get_cfdi(uuid):
    cache = load_cache()
    uuid_upper = uuid.upper()
    
    for c in cache.get('recibidos', []) + cache.get('emitidos', []):
        if c.get('uuid', '').upper() == uuid_upper:
            return jsonify(c)
    return jsonify({"error": "CFDI no encontrado. Intenta sincronizar primero con POST /sync"}), 404

@app.route('/emitidos')
def list_emitidos():
    cache = load_cache()
    emitidos = cache.get('emitidos', [])
    total = sum(float(c.get('monto', 0)) for c in emitidos)
    
    return jsonify({
        "rfc": "MUTM8610091NA",
        "total_emitidos": len(emitidos),
        "total_monto": round(total, 2),
        "cfdis": emitidos,
        "last_sync": cache.get('last_sync')
    })

@app.route('/emitir', methods=['POST'])
def emitir():
    """
    Emitir factura CFDI 4.0 usando SAT gratuito (portal SAT).
    Requiere FIEL del vault para autenticación.
    """
    connector = sat_connector()
    if not connector:
        return jsonify({"status": "error", "message": "SAT connector no disponible"}), 500
    
    data = request.json or {}
    
    required = ['rfc_receptor', 'nombre_receptor', 'codigo_postal', 'concepto',
                'cantidad', 'precio_unitario']
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"status": "error", "message": f"Campos requeridos faltantes: {', '.join(missing)}"}), 400
    
    try:
        if not connector._is_connected:
            auth_ok = connector.authenticate()
            if not auth_ok:
                return jsonify({"status": "error", "message": "Autenticación FIEL fallida"}), 401
        
        from satcfdi.models import CFDI
        from satcfdi import cfdi
        from satcfdi.pacs.sat import SAT
        
        cantidad = float(data.get('cantidad', 1))
        precio_unitario = float(data.get('precio_unitario', 0))
        subtotal = cantidad * precio_unitario
        iva = subtotal * 0.16
        total = subtotal + iva
        
        # Build CFDI 4.0 using satcfdi
        fecha_emision = datetime.now()
        
        cfdi_doc = cfdi.CFDI(
            Version="4.0",
            Serie=data.get('serie', 'F'),
            Folio=data.get('folio', str(int(time.time()))),
            Fecha=fecha_emision.strftime('%Y-%m-%dT%H:%M:%S'),
            FormaPago=data.get('forma_pago', '03'),
            CondicionesDePago=data.get('condiciones_pago', 'Contado'),
            SubTotal=round(subtotal, 2),
            Moneda='MXN',
            TipoCambio=1,
            Total=round(total, 2),
            TipoDeComprobante='I',
            MetodoPago=data.get('metodo_pago', 'PUE'),
            LugarExpedicion=data.get('lugar_expedicion', data.get('codigo_postal', '63700')),
            Exportacion='01',
        )
        
        cfdi_doc.add_emisor(
            Rfc=connector.rfc,
            Nombre="MARCO ARTURO MUÑOZ DEL TORO",
            RegimenFiscal=data.get('regimen_fiscal_emisor', '612'),
        )
        
        cfdi_doc.add_receptor(
            Rfc=data['rfc_receptor'],
            Nombre=data['nombre_receptor'],
            DomicilioFiscalReceptor=data['codigo_postal'],
            RegimenFiscalReceptor=data.get('regimen_fiscal_receptor', '601'),
            UsoCFDI=data.get('uso_cfdi', 'G03'),
        )
        
        cfdi_doc.add_concepto(
            ClaveProdServ=data.get('clave_prod_serv', '01010101'),
            Cantidad=cantidad,
            ClaveUnidad=data.get('clave_unidad', 'E48'),
            Descripcion=data['concepto'],
            ValorUnitario=round(precio_unitario, 2),
            Importe=round(subtotal, 2),
            ObjetoImp='02',
        )
        
        # Sign with FIEL
        cfdi_doc.sign(connector.signer)
        
        # Stamp via SAT portal (gratuito)
        sat = SAT(connector.signer)
        result = sat.stamp(cfdi_doc)
        
        # Extract UUID from stamped CFDI
        uuid_timbrado = None
        xml_timbrado = None
        if hasattr(result, 'uuid'):
            uuid_timbrado = result.uuid
        elif isinstance(result, dict):
            uuid_timbrado = result.get('uuid')
            xml_timbrado = result.get('xml')
        
        # Update emitidos cache
        cache = load_cache()
        new_cfdi = {
            'uuid': uuid_timbrado,
            'rfc_emisor': connector.rfc,
            'nombre_emisor': 'MARCO ARTURO MUÑOZ DEL TORO',
            'rfc_receptor': data['rfc_receptor'],
            'nombre_receptor': data['nombre_receptor'],
            'monto': round(total, 2),
            'subtotal': round(subtotal, 2),
            'iva': round(iva, 2),
            'fecha_emision': fecha_emision.isoformat(),
            'tipo_comprobante': 'I',
            'estatus': '1',
            'version': '4.0'
        }
        cache.setdefault('emitidos', []).append(new_cfdi)
        cache['last_sync'] = datetime.now().isoformat()
        save_cache(cache)
        
        return jsonify({
            "status": "success",
            "message": "CFDI 4.0 emitido y timbrado via SAT gratuito",
            "uuid": uuid_timbrado,
            "totales": {
                "subtotal": round(subtotal, 2),
                "iva": round(iva, 2),
                "total": round(total, 2)
            },
            "fecha": fecha_emision.isoformat(),
            "xml_disponible": f"/cfdis/{uuid_timbrado}/xml" if uuid_timbrado else None
        })
        
    except AttributeError as e:
        logger.error(f"Emitir CFDI attribute error: {e}")
        return jsonify({
            "status": "partial",
            "message": "CFDI generado pero timbrado requiere ajuste de API satcfdi",
            "error": str(e),
            "note": "Verificar método stamp() de satcfdi.pacs.sat.SAT"
        }), 202
    except Exception as e:
        logger.error(f"Emitir CFDI failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/cancelar', methods=['POST'])
def cancelar():
    """Cancelar factura via SAT real"""
    connector = sat_connector()
    if not connector:
        return jsonify({"status": "error", "message": "SAT connector no disponible"}), 500
    
    data = request.json or {}
    uuid_cancelar = data.get('uuid')
    motivo = data.get('motivo', '02')  # 02 = Comprobante emitido con errores
    uuid_relativo = data.get('uuid_relacionado')
    
    if not uuid_cancelar:
        return jsonify({"status": "error", "message": "UUID requerido"}), 400
    
    try:
        if not connector._is_connected:
            auth_ok = connector.authenticate()
            if not auth_ok:
                return jsonify({"status": "error", "message": "Autenticación FIEL fallida"}), 401
        
        from satcfdi.pacs.sat import SAT
        sat = SAT(connector.signer)
        
        result = sat.cancel(
            rfc_emisor=connector.rfc,
            uuid=uuid_cancelar,
            motivo=motivo,
            uuid_relativo=uuid_relativo
        )
        
        return jsonify({
            "status": "success",
            "message": f"Solicitud de cancelación enviada para {uuid_cancelar}",
            "uuid": uuid_cancelar,
            "result": str(result) if not isinstance(result, dict) else result
        })
        
    except Exception as e:
        logger.error(f"Cancel failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/opinion')
def opinion_cumplimiento():
    """Opinión de cumplimiento SAT"""
    connector = sat_connector()
    if not connector:
        return jsonify({"status": "error", "message": "SAT connector no disponible"}), 500
    
    try:
        if not connector._is_connected:
            connector.authenticate()
        
        opinion = connector.get_compliance_opinion()
        return jsonify(opinion)
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/obligaciones')
def obligaciones():
    """Get fiscal obligations based on current date"""
    today = date.today()
    year = today.year
    month = today.month
    day = today.day
    
    obligations = []
    
    # Monthly declarations - ISR/IVA (day 17)
    if day <= 17:
        days_to_17 = 17 - day
        urgency = 'critical' if days_to_17 <= 3 else ('high' if days_to_17 <= 7 else 'normal')
        obligations.append({
            'id': 'iva-isr-mensual',
            'titulo': f'IVA + ISR - {MONTH_NAMES[str(month).zfill(2)]} {year}',
            'tipo': 'Mensual',
            'vence': f'{year}-{str(month).zfill(2)}-17',
            'dias_restantes': days_to_17,
            'urgencia': urgency,
            'descripcion': 'Declaración mensual de IVA e ISR.',
            'accion': 'Presenta antes del 17',
            'penalizacion': 'Recargos 1.47% + multa 20%'
        })
    else:
        next_m = month + 1 if month < 12 else 1
        next_y = year if month < 12 else year + 1
        days_to_next = 47 - day
        obligations.append({
            'id': 'iva-isr-mensual',
            'titulo': f'IVA + ISR - {MONTH_NAMES[str(next_m).zfill(2)]} {next_y}',
            'tipo': 'Mensual',
            'vence': f'{next_y}-{str(next_m).zfill(2)}-17',
            'dias_restantes': days_to_next,
            'urgencia': 'normal',
            'descripcion': 'Próxima declaración.',
            'accion': 'Prepara tus CFDIs',
            'penalizacion': None
        })
    
    # Annual declaration
    if month <= 4:
        days_to_april_30 = (date(year, 4, 30) - today).days
        if days_to_april_30 > 0:
            urgency = 'critical' if days_to_april_30 <= 7 else ('high' if days_to_april_30 <= 21 else 'normal')
            obligations.append({
                'id': 'declaracion-anual',
                'titulo': f'Declaración Anual {year-1}',
                'tipo': 'Anual',
                'vence': f'{year}-04-30',
                'dias_restantes': days_to_april_30,
                'urgencia': urgency,
                'descripcion': 'Declaración Anual de Personas Físicas.',
                'accion': 'Revisa deducciones personales',
                'penalizacion': 'Multa hasta 40%'
            })
    
    # Contabilidad electrónica
    if day <= 15:
        obligations.append({
            'id': 'contabilidad-electronica',
            'titulo': 'Contabilidad Electrónica',
            'tipo': 'Mensual',
            'vence': f'{year}-{str(month).zfill(2)}-15',
            'dias_restantes': 15 - day,
            'urgencia': 'normal' if day <= 10 else 'high',
            'descripcion': 'Envío de XML de pólizas y auxiliares.',
            'accion': 'Genera XML desde tu sistema',
            'penalizacion': 'Multa $6,380-$11,870'
        })
    
    # Sort by urgency
    urgency_order = {'critical': 0, 'overdue': 1, 'high': 2, 'normal': 3, 'low': 4}
    obligations.sort(key=lambda x: urgency_order.get(x['urgencia'], 5))
    
    return jsonify({
        'rfc': 'MUTM8610091NA',
        'fecha_actual': today.isoformat(),
        'obligaciones_pendientes': obligations,
        'resumen': {
            'criticas': sum(1 for o in obligations if o['urgencia'] == 'critical'),
            'altas': sum(1 for o in obligations if o['urgencia'] == 'high'),
            'normales': sum(1 for o in obligations if o['urgencia'] == 'normal'),
            'total': len(obligations)
        }
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)