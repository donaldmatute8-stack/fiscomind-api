#!/usr/bin/env python3
"""
FiscoMind Railway API v4.1 - Based on working local version
- Same SAT calls as local api_server.py
- METADATA + EstadoComprobante.TODOS
- recover_comprobante_issued_request (not emitted)
- Parse base64→ZIP→CSV (METADATA format)
"""
import os
import sys
import json
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict

from flask import Flask, jsonify, request
from flask_cors import CORS

sys.path.insert(0, str(Path(__file__).parent / 'src'))

app = Flask(__name__)
CORS(app, origins=["*"], supports_credentials=True)

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fiscomind-api")

DATA_DIR = Path(os.environ.get('DATA_DIR', '/app/data'))
DATA_DIR.mkdir(exist_ok=True, parents=True)
CACHE_FILE = DATA_DIR / 'cfdi_cache.json'

MONTH_NAMES = {
    '01': 'Enero', '02': 'Febrero', '03': 'Marzo', '04': 'Abril',
    '05': 'Mayo', '06': 'Junio', '07': 'Julio', '08': 'Agosto',
    '09': 'Septiembre', '10': 'Octubre', '11': 'Noviembre', '12': 'Diciembre'
}

# ─── SAT Connector (lazy) ──────────────────────────────────────────

_sat_connector = None

def sat_connector():
    global _sat_connector
    if _sat_connector is None:
        try:
            from sat_connector_real import SATConnectorReal
            _sat_connector = SATConnectorReal(rfc="MUTM8610091NA")
            logger.info(f"SAT connector created. Vault: {_sat_connector.vault.VAULT_DIR}")
        except Exception as e:
            logger.error(f"SAT connector error: {e}", exc_info=True)
    return _sat_connector

# ─── Cache ──────────────────────────────────────────────────────────

def load_cache():
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text())
        except:
            pass
    return {"last_sync": None, "recibidos": [], "emitidos": [], "pending_requests": {}}

def save_cache(data):
    CACHE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str))

# ─── Routes ─────────────────────────────────────────────────────────

@app.route('/')
def index():
    return jsonify({
        "name": "FiscoMind API",
        "version": "4.1.0",
        "status": "running",
        "mode": "REAL",
        "endpoints": {
            "GET /": "Info",
            "GET /health": "Health check",
            "GET /dashboard": "Dashboard fiscal (datos reales)",
            "POST /sync": "Submit CFDI download request (async)",
            "POST /sync/check": "Check pending requests & download",
            "GET /cfdis": "Lista CFDIs",
            "GET /emitidos": "Facturas emitidas",
            "POST /emitir": "Emitir factura CFDI 4.0",
            "POST /cancelar": "Cancelar factura",
            "GET /obligaciones": "Obligaciones fiscales",
            "GET /opinion": "Opinión de cumplimiento SAT"
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
    
    total_ingresos = sum(float(c.get('monto', 0)) for c in recibidos if c.get('efecto') == 'I' and c.get('estatus') == '1')
    total_egresos = sum(float(c.get('monto', 0)) for c in recibidos if c.get('efecto') == 'E' and c.get('estatus') == '1')
    total_emitidos = sum(float(c.get('monto', 0)) for c in emitidos if c.get('estatus') == '1')
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
        "recent_cfdis": sorted(recibidos + emitidos, key=lambda x: x.get('fecha_emision', ''), reverse=True)[:20]
    })

@app.route('/sync', methods=['POST'])
def sync():
    """Submit CFDI download request to SAT (returns immediately)"""
    connector = sat_connector()
    if not connector:
        return jsonify({"status": "error", "message": "SAT connector no disponible"}), 500
    
    data = request.json or {}
    date_start = data.get('date_start', (date.today() - timedelta(days=90)).isoformat())
    date_end = data.get('date_end', date.today().isoformat())
    tipo = data.get('tipo', 'recibidos')
    
    try:
        if not connector._is_connected:
            if not connector.authenticate():
                return jsonify({"status": "error", "message": "Autenticación FIEL fallida"}), 401
        
        result = connector.submit_download_request(date_start, date_end, tipo)
        
        if result.get('status') == 'submitted':
            cache = load_cache()
            cache.setdefault('pending_requests', {})[result['id_solicitud']] = {
                'id_solicitud': result['id_solicitud'],
                'tipo': tipo,
                'date_start': date_start,
                'date_end': date_end,
                'submitted': datetime.now().isoformat()
            }
            save_cache(cache)
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Sync failed: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/sync/check', methods=['POST'])
def sync_check():
    """Check pending requests and download CFDIs if ready"""
    connector = sat_connector()
    if not connector:
        return jsonify({"status": "error", "message": "SAT connector no disponible"}), 500
    
    data = request.json or {}
    id_solicitud = data.get('id_solicitud')
    
    try:
        if not connector._is_connected:
            if not connector.authenticate():
                return jsonify({"status": "error", "message": "Not authenticated"}), 401
        
        cache = load_cache()
        pending = cache.get('pending_requests', {})
        
        if id_solicitud:
            # Check specific request
            status = connector.check_request_status(id_solicitud)
            if status.get('finished'):
                cfdis = status.get('cfdis', [])
                if cfdis:
                    req_info = pending.get(id_solicitud, {})
                    key = 'recibidos' if req_info.get('tipo') == 'recibidos' else 'emitidos'
                    cache.setdefault(key, []).extend(cfdis)
                    cache['last_sync'] = datetime.now().isoformat()
                    if id_solicitud in pending:
                        del pending[id_solicitud]
                    cache['pending_requests'] = pending
                    save_cache(cache)
            return jsonify(status)
        
        # Check all pending
        if not pending:
            return jsonify({"status": "success", "message": "No pending requests", "pending": 0})
        
        results = []
        for req_id in list(pending.keys()):
            status = connector.check_request_status(req_id)
            results.append(status)
            
            if status.get('finished'):
                cfdis = status.get('cfdis', [])
                if cfdis:
                    req_info = pending[req_id]
                    key = 'recibidos' if req_info.get('tipo') == 'recibidos' else 'emitidos'
                    cache.setdefault(key, []).extend(cfdis)
                    cache['last_sync'] = datetime.now().isoformat()
                if req_id in pending:
                    del pending[req_id]
        
        cache['pending_requests'] = pending
        save_cache(cache)
        
        return jsonify({
            "status": "success",
            "checked": len(results),
            "results": results
        })
    
    except Exception as e:
        logger.error(f"Sync check failed: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/cfdis')
def list_cfdis():
    cache = load_cache()
    tipo = request.args.get('tipo', 'all')
    cfdis = []
    if tipo in ['all', 'recibidos']:
        cfdis.extend(cache.get('recibidos', []))
    if tipo in ['all', 'emitidos']:
        cfdis.extend(cache.get('emitidos', []))
    return jsonify({"rfc": "MUTM8610091NA", "tipo": tipo, "total": len(cfdis), "cfdis": cfdis})

@app.route('/emitidos')
def list_emitidos():
    cache = load_cache()
    emitidos = cache.get('emitidos', [])
    total = sum(float(c.get('monto', 0)) for c in emitidos)
    return jsonify({"rfc": "MUTM8610091NA", "total_emitidos": len(emitidos), "total_monto": round(total, 2), "cfdis": emitidos})

@app.route('/emitir', methods=['POST'])
def emitir():
    data = request.json or {}
    return jsonify({"status": "pending", "message": "Emisión CFDI 4.0 - requiere timbrado SAT gratuito", "data_received": data})

@app.route('/cancelar', methods=['POST'])
def cancelar():
    data = request.json or {}
    return jsonify({"status": "pending", "message": "Cancelación requiere SAT", "uuid": data.get('uuid')})

@app.route('/opinion')
def opinion_cumplimiento():
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
    today = date.today()
    year, month, day = today.year, today.month, today.day
    
    obligations = []
    
    if day <= 17:
        days_to_17 = 17 - day
        urgency = 'critical' if days_to_17 <= 3 else ('high' if days_to_17 <= 7 else 'normal')
        obligations.append({
            'id': 'iva-isr-mensual',
            'titulo': f'IVA + ISR - {MONTH_NAMES[str(month).zfill(2)]} {year}',
            'tipo': 'Mensual', 'vence': f'{year}-{str(month).zfill(2)}-17',
            'dias_restantes': days_to_17, 'urgencia': urgency,
            'descripcion': 'Declaración mensual de IVA e ISR.',
            'accion': 'Presenta antes del 17'
        })
    else:
        next_m = month + 1 if month < 12 else 1
        next_y = year if month < 12 else year + 1
        obligations.append({
            'id': 'iva-isr-mensual',
            'titulo': f'IVA + ISR - {MONTH_NAMES[str(next_m).zfill(2)]} {next_y}',
            'tipo': 'Mensual', 'vence': f'{next_y}-{str(next_m).zfill(2)}-17',
            'dias_restantes': 47 - day, 'urgencia': 'normal',
            'descripcion': 'Próxima declaración.'
        })
    
    if month <= 4:
        days_to_april_30 = (date(year, 4, 30) - today).days
        if days_to_april_30 > 0:
            urgency = 'critical' if days_to_april_30 <= 7 else ('high' if days_to_april_30 <= 21 else 'normal')
            obligations.append({
                'id': 'declaracion-anual', 'titulo': f'Declaración Anual {year-1}',
                'tipo': 'Anual', 'vence': f'{year}-04-30',
                'dias_restantes': days_to_april_30, 'urgencia': urgency
            })
    
    urgency_order = {'critical': 0, 'overdue': 1, 'high': 2, 'normal': 3, 'low': 4}
    obligations.sort(key=lambda x: urgency_order.get(x['urgencia'], 5))
    
    return jsonify({
        'rfc': 'MUTM8610091NA', 'fecha_actual': today.isoformat(),
        'obligaciones_pendientes': obligations,
        'resumen': {
            'criticas': sum(1 for o in obligations if o['urgencia'] == 'critical'),
            'altas': sum(1 for o in obligations if o['urgencia'] == 'high'),
            'total': len(obligations)
        }
    })

@app.route('/complemento-pago', methods=['POST'])
def complemento_pago():
    """Generar complemento de pago para una factura PPD"""
    data = request.json or {}
    factura_uuid = data.get('factura_uuid')
    monto_pagado = data.get('monto_pagado', 0)
    fecha_pago = data.get('fecha_pago')
    forma_pago = data.get('forma_pago', '03')
    
    if not factura_uuid:
        return jsonify({"status": "error", "message": "UUID de factura requerido"}), 400
    
    cache = load_cache()
    emitidos = cache.get('emitidos', [])
    
    # Find the original invoice
    factura = next((c for c in emitidos if c.get('uuid') == factura_uuid), None)
    if not factura:
        return jsonify({"status": "error", "message": "Factura no encontrada"}), 404
    
    # Initialize complementos list if not exists
    if 'complementos' not in factura:
        factura['complementos'] = []
    
    # Calculate total paid so far
    total_pagado = sum(c.get('monto_pagado', 0) for c in factura.get('complementos', []))
    total_pagado += float(monto_pagado)
    
    # Create complemento record
    complemento = {
        'uuid': str(uuid.uuid4()).upper(),
        'tipo': 'P',
        'factura_relacionada': factura_uuid,
        'monto_pagado': float(monto_pagado),
        'fecha_pago': fecha_pago,
        'forma_pago': forma_pago,
        'fecha_generacion': datetime.now().isoformat(),
        'estatus': '1'
    }
    
    factura['complementos'].append(complemento)
    
    # Update payment status
    factura['total_pagado'] = total_pagado
    factura['saldo_pendiente'] = float(factura.get('monto', 0)) - total_pagado
    
    save_cache(cache)
    
    return jsonify({
        "status": "success",
        "message": "Complemento de pago generado",
        "complemento": complemento,
        "factura": {
            "uuid": factura_uuid,
            "total": factura.get('monto'),
            "pagado": total_pagado,
            "pendiente": factura['saldo_pendiente']
        }
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)