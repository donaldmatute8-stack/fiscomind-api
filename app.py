#!/usr/bin/env python3
"""
FiscoMind Railway API v3.0
API completa para SAT con soporte para:
- Sincronización CFDIs
- Emisión facturas (SAT gratuito)
- Cancelación
- Descarga XML/PDF
"""
import os
import sys
import json
import base64
import io
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins=["*"], supports_credentials=True)

# Data directory (persistente en Railway)
DATA_DIR = Path(os.environ.get('DATA_DIR', '/tmp/fiscomind-data'))
DATA_DIR.mkdir(exist_ok=True, parents=True)

# In-memory storage for demo (reemplazar con DB en producción)
_users_db = {}
_cfdis_db = {}

# Sample data for Marco
SAMPLE_DATA = {
    "marco_test": {
        "rfc": "MUTM8610091NA",
        "nombre": "MARCO ARTURO MUÑOZ DEL TORO",
        "cfdis_recibidos": [
            {"uuid": "9C07F8DE-9DD3-4C60-9EE7-238F02D1F7C0", "rfc_emisor": "BRM940216EQ6", "nombre_emisor": "BANCO REGIONAL SA", "rfc_receptor": "MUTM8610091NA", "monto": 150.80, "fecha_emision": "2026-04-03", "efecto": "I", "estatus": "1"},
            {"uuid": "D6BBE9EF-7582-49DA-BB17-9B344DDD789B", "rfc_emisor": "CNM980114PI2", "nombre_emisor": "AT&T COMUNICACIONES", "rfc_receptor": "MUTM8610091NA", "monto": 804.04, "fecha_emision": "2026-04-15", "efecto": "I", "estatus": "1"},
            {"uuid": "6D175680-B5C2-48B0-B8A3-8FC53FB3337F", "rfc_emisor": "CNM980114PI2", "nombre_emisor": "AT&T COMUNICACIONES", "rfc_receptor": "MUTM8610091NA", "monto": 372.41, "fecha_emision": "2026-04-15", "efecto": "E", "estatus": "1"},
        ],
        "cfdis_emitidos": [
            {"uuid": "CE113741", "rfc_emisor": "MUTM8610091NA", "nombre_emisor": "MARCO ARTURO MUÑOZ DEL TORO", "rfc_receptor": "BENITTOS", "nombre_receptor": "BENITTOS FOOD PARTY", "monto": 8352.00, "fecha_emision": "2026-04-01", "efecto": "I", "estatus": "1"},
            {"uuid": "CF0741C5", "rfc_emisor": "MUTM8610091NA", "nombre_emisor": "MARCO ARTURO MUÑOZ DEL TORO", "rfc_receptor": "BENITTOS", "nombre_receptor": "BENITTOS FOOD PARTY", "monto": 41669.85, "fecha_emision": "2026-04-15", "efecto": "I", "estatus": "1"},
            {"uuid": "26072D49", "rfc_emisor": "MUTM8610091NA", "nombre_emisor": "MARCO ARTURO MUÑOZ DEL TORO", "rfc_receptor": "BENITTOS", "nombre_receptor": "BENITTOS FOOD PARTY", "monto": 45889.60, "fecha_emision": "2026-05-01", "efecto": "I", "estatus": "1"},
            {"uuid": "DA4E4E23", "rfc_emisor": "MUTM8610091NA", "nombre_emisor": "MARCO ARTURO MUÑOZ DEL TORO", "rfc_receptor": "BENITTOS", "nombre_receptor": "BENITTOS FOOD PARTY", "monto": 66816.00, "fecha_emision": "2026-05-08", "efecto": "I", "estatus": "1"},
        ]
    }
}

@app.route('/')
def index():
    return jsonify({
        "name": "FiscoMind API",
        "version": "3.0.0",
        "status": "running",
        "endpoints": {
            "GET /": "Info",
            "GET /health": "Health check",
            "GET /dashboard": "Dashboard fiscal",
            "POST /sync": "Sincronizar con SAT",
            "GET /cfdis": "Lista CFDIs",
            "GET /cfdis/<uuid>": "Detalle CFDI",
            "GET /emitidos": "Facturas emitidas",
            "POST /emitir": "Emitir factura",
            "POST /cancelar": "Cancelar factura",
        }
    })

@app.route('/health')
def health():
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})

@app.route('/dashboard')
def dashboard():
    user_id = request.args.get('user_id', 'default')
    data = SAMPLE_DATA.get(user_id, SAMPLE_DATA['marco_test'])
    
    recibidos = data['cfdis_recibidos']
    emitidos = data['cfdis_emitidos']
    
    total_ingresos = sum(c['monto'] for c in recibidos if c['efecto'] == 'I')
    total_egresos = sum(c['monto'] for c in recibidos if c['efecto'] == 'E')
    total_emitidos = sum(c['monto'] for c in emitidos)
    
    return jsonify({
        "rfc": data['rfc'],
        "user_id": user_id,
        "last_sync": "2026-05-11",
        "summary": {
            "total_recibidos": len(recibidos),
            "total_emitidos": len(emitidos),
            "total_ingresos": total_ingresos,
            "total_egresos": total_egresos,
            "total_emitido_monto": total_emitidos,
            "ahorro_isr_estimado": total_ingresos * 0.30
        },
        "recent_cfdis": recibidos + emitidos
    })

@app.route('/sync', methods=['POST'])
def sync():
    user_id = request.args.get('user_id') or request.json.get('user_id', 'default')
    return jsonify({
        "status": "requested",
        "message": "Sincronización iniciada (demo mode)",
        "user_id": user_id,
        "note": "En producción conecta con SAT real"
    })

@app.route('/cfdis')
def list_cfdis():
    user_id = request.args.get('user_id', 'default')
    tipo = request.args.get('tipo', 'all')
    data = SAMPLE_DATA.get(user_id, SAMPLE_DATA['marco_test'])
    
    cfdis = []
    if tipo in ['all', 'recibidos']:
        cfdis.extend(data['cfdis_recibidos'])
    if tipo in ['all', 'emitidos']:
        cfdis.extend(data['cfdis_emitidos'])
    
    return jsonify({
        "rfc": data['rfc'],
        "tipo": tipo,
        "total": len(cfdis),
        "cfdis": cfdis
    })

@app.route('/cfdis/<uuid>')
def get_cfdi(uuid):
    user_id = request.args.get('user_id', 'default')
    data = SAMPLE_DATA.get(user_id, SAMPLE_DATA['marco_test'])
    
    for c in data['cfdis_recibidos'] + data['cfdis_emitidos']:
        if c['uuid'].upper() == uuid.upper():
            return jsonify(c)
    return jsonify({"error": "CFDI no encontrado"}), 404

@app.route('/emitidos')
def list_emitidos():
    user_id = request.args.get('user_id', 'default')
    data = SAMPLE_DATA.get(user_id, SAMPLE_DATA['marco_test'])
    emitidos = data['cfdis_emitidos']
    total = sum(c['monto'] for c in emitidos)
    
    return jsonify({
        "rfc": data['rfc'],
        "total_emitidos": len(emitidos),
        "total_monto": total,
        "cfdis": emitidos
    })

@app.route('/emitir', methods=['POST'])
def emitir():
    """Emitir factura - requiere conexión SAT real"""
    data = request.json or {}
    return jsonify({
        "status": "pending",
        "message": "Emisión requiere integración con SAT",
        "note": "Para producción: integrar con servicio gratuito SAT o PAC",
        "data_received": data
    })

@app.route('/cancelar', methods=['POST'])
def cancelar():
    """Cancelar factura"""
    data = request.json or {}
    return jsonify({
        "status": "pending", 
        "message": "Cancelación requiere integración con SAT",
        "uuid": data.get('uuid'),
        "motivo": data.get('motivo')
    })

@app.route('/obligaciones')
def obligaciones():
    """Get fiscal obligations based on current date"""
    from datetime import date, timedelta
    
    today = date.today()
    year = today.year
    month = today.month
    day = today.day
    
    obligations = []
    
    # Monthly declarations - ISR/IVA (day 17)
    days_to_17 = 17 - day if day <= 17 else (17 + 30 - day)
    if days_to_17 <= 5:
        urgency = 'critical' if days_to_17 <= 3 else 'high'
        obligations.append({
            'id': 'iva-isr-mensual',
            'titulo': f'IVA + ISR Provisional - {MONTH_NAMES.get(str(month).zfill(2), month)} {year}',
            'tipo': 'Mensual',
            'vence': f'{year}-{str(month).zfill(2)}-17',
            'dias_restantes': days_to_17,
            'urgencia': urgency,
            'descripcion': f'Declaración mensual de IVA e ISR. Vence el día 17 de {MONTH_NAMES.get(str(month).zfill(2), month)}.',
            'accion_recomendada': 'Presenta tu declaración antes de la fecha límite para evitar recargos.',
            'penalizacion': 'Recargos del 1.47% mensual + multa del 20%',
            'monto_estimado': None  # Calculado dinámicamente si hay datos
        })
    else:
        obligations.append({
            'id': 'iva-isr-mensual',
            'titulo': f'IVA + ISR Provisional - {MONTH_NAMES.get(str(month).zfill(2), month)} {year}',
            'tipo': 'Mensual',
            'vence': f'{year}-{str(month).zfill(2)}-17',
            'dias_restantes': days_to_17,
            'urgencia': 'normal',
            'descripcion': f'Declaración mensual de IVA e ISR.',
            'accion_recomendada': 'Prepara tus CFDIs para deducciones.',
            'penalizacion': None,
            'monto_estimado': None
        })
    
    # Next month preview
    next_m = month + 1 if month < 12 else 1
    next_y = year if month < 12 else year + 1
    obligations.append({
        'id': 'iva-isr-proximo',
        'titulo': f'IVA + ISR Provisional - {MONTH_NAMES.get(str(next_m).zfill(2), next_m)} {next_y}',
        'tipo': 'Mensual',
        'vence': f'{next_y}-{str(next_m).zfill(2)}-17',
        'dias_restantes': days_to_17 + 30,
        'urgencia': 'low',
        'descripcion': f'Próxima declaración mensual.',
        'accion_recomendada': 'Acumula deducciones.',
        'penalizacion': None,
        'monto_estimado': None
    })
    
    # Quarterly - IETU (if applicable, for certain regimes)
    if month in [3, 6, 9, 12]:
        last_day = {3: 31, 6: 30, 9: 30, 12: 31}[month]
        days_to_end = last_day - day
        if days_to_end <= 10:
            obligations.append({
                'id': f'ietu-trimestre-{month//3}',
                'titulo': f'IETU Trimestral - T{month//3} {year}',
                'tipo': 'Trimestral',
                'vence': f'{year}-{str(month).zfill(2)}-{last_day}',
                'dias_restantes': days_to_end,
                'urgencia': 'high' if days_to_end <= 5 else 'normal',
                'descripcion': f'Declaración trimestral de IETU.',
                'accion_recomendada': 'Verifica si aplica a tu régimen fiscal.',
                'penalizacion': 'Recargos por presentación extemporánea',
                'monto_estimado': None
            })
    
    # Annual declaration - April 30
    if month <= 4:
        days_to_april_30 = (date(year, 4, 30) - today).days
        if days_to_april_30 > 0:
            urgency = 'critical' if days_to_april_30 <= 7 else ('high' if days_to_april_30 <= 15 else 'normal')
            obligations.append({
                'id': 'declaracion-anual',
                'titulo': f'Declaración Anual {year}',
                'tipo': 'Anual',
                'vence': f'{year}-04-30',
                'dias_restantes': days_to_april_30,
                'urgencia': urgency,
                'descripcion': 'Declaración Anual de Personas Físicas. Obligatorio para todos los contribuyentes.',
                'accion_recomendada': 'Revisa todas tus deducciones personales y reembolsos.',
                'penalizacion': 'Multa de hasta 40% del impuesto omitido + recargos',
                'monto_estimado': None
            })
    
    # Monthly accounting submission (some regimes require this)
    obligations.append({
        'id': 'contabilidad-electronica',
        'titulo': f'Contabilidad Electrónica - {MONTH_NAMES.get(str(month).zfill(2), month)} {year}',
        'tipo': 'Mensual',
        'vence': f'{year}-{str(month).zfill(2)}-15',
        'dias_restantes': 15 - day if day <= 15 else 0,
        'urgencia': 'normal' if day <= 15 else 'overdue',
        'descripcion': 'Envío de contabilidad electrónica (XML de pólizas y auxiliares).',
        'accion_recomendada': 'Genera XML de contabilidad desde tu sistema.',
        'penalizacion': 'Multa de $6,380 a $11,870 UMA',
        'monto_estimado': None
    })
    
    # Digital tax receipt - periodic obligations
    obligations.append({
        'id': 'cfdi-emitidos',
        'titulo': 'Facturas Emitidas',
        'tipo': 'Continua',
        'vence': 'N/A',
        'dias_restantes': 0,
        'urgencia': 'low',
        'descripcion': 'Emisión de CFDIs para clientes.',
        'accion_recomendada': 'Emite facturas dentro de 72h de cobro.',
        'penalizacion': 'Multa por no emitir CFDI: $3,190 a $11,870',
        'monto_estimado': None
    })
    
    # Sort by urgency
    urgency_order = {'critical': 0, 'overdue': 1, 'high': 2, 'normal': 3, 'low': 4}
    obligations.sort(key=lambda x: urgency_order.get(x['urgencia'], 5))
    
    return jsonify({
        'rfc': SAMPLE_DATA['marco_test']['rfc'],
        'fecha_actual': today.isoformat(),
        'obligaciones_pendientes': obligations,
        'resumen': {
            'criticas': sum(1 for o in obligations if o['urgencia'] == 'critical'),
            'altas': sum(1 for o in obligations if o['urgencia'] == 'high'),
            'normales': sum(1 for o in obligations if o['urgencia'] == 'normal'),
            'total': len(obligations)
        }
    })

@app.route('/obligaciones')
def obligaciones():
    """Get fiscal obligations based on current date"""
    from datetime import date, timedelta
    
    today = date.today()
    year = today.year
    month = today.month
    day = today.day
    
    MONTH_NAMES = {
        '01': 'Enero', '02': 'Febrero', '03': 'Marzo', '04': 'Abril',
        '05': 'Mayo', '06': 'Junio', '07': 'Julio', '08': 'Agosto',
        '09': 'Septiembre', '10': 'Octubre', '11': 'Noviembre', '12': 'Diciembre'
    }
    
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
            'descripcion': f'Declaración mensual de IVA e ISR.',
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
            'descripcion': f'Próxima declaración.',
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
            'titulo': f'Contabilidad Electrónica',
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
        'rfc': SAMPLE_DATA['marco_test']['rfc'],
        'fecha_actual': today.isoformat(),
        'obligaciones_pendientes': obligations,
        'resumen': {
            'criticas': sum(1 for o in obligations if o['urgencia'] == 'critical'),
            'altas': sum(1 for o in obligations if o['urgencia'] == 'high'),
            'normales': sum(1 for o in obligations if o['urgencia'] == 'normal'),
            'total': len(obligations)
        }
    })

@app.route('/emitir-factura', methods=['POST'])
def emitir_factura():
    """
    Emitir factura CFDI 4.0 usando SAT gratuito
    Requiere FIEL para autenticación
    
    Campos requeridos:
    - rfc_receptor: str (13 chars)
    - nombre_receptor: str
    - codigo_postal: str (5 digits)
    - regimen_fiscal: str (código SAT)
    - uso_cfdi: str (código SAT, ej: G03 para gastos)
    - concepto: str (descripción del producto/servicio)
    - cantidad: number
    - precio_unitario: number
    - forma_pago: str (código SAT, ej: 03 transferencia)
    - metodo_pago: str (código SAT, ej: PUE - Pago en una sola exhibición)
    """
    data = request.json or {}
    
    # Validate required fields
    required = ['rfc_receptor', 'nombre_receptor', 'codigo_postal', 'concepto', 
                'cantidad', 'precio_unitario']
    missing = [f for f in required if not data.get(f)]
    
    if missing:
        return jsonify({
            'status': 'error',
            'message': f'Campos requeridos faltantes: {", ".join(missing)}'
        }), 400
    
    # Calculate totals
    cantidad = float(data.get('cantidad', 1))
    precio_unitario = float(data.get('precio_unitario', 0))
    subtotal = cantidad * precio_unitario
    iva = subtotal * 0.16  # IVA 16%
    total = subtotal + iva
    
    # Build CFDI 4.0 structure (XML)
    from datetime import datetime
    
    fecha_emision = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    
    cfdi_data = {
        'uuid': None,  # Se genera al timbrar
        'version': '4.0',
        'serie': data.get('serie', 'F'),
        'folio': data.get('folio', '1'),
        'fecha': fecha_emision,
        'forma_pago': data.get('forma_pago', '03'),  # Transferencia electrónica
        'condiciones_pago': data.get('condiciones_pago', 'Contado'),
        'subtotal': round(subtotal, 2),
        'moneda': 'MXN',
        'tipo_cambio': 1,
        'total': round(total, 2),
        'tipo_comprobante': 'I',  # Ingreso
        'metodo_pago': data.get('metodo_pago', 'PUE'),
        'lugar_expedicion': data.get('lugar_expedicion', '01000'),  # CP emisor
        'exportacion': data.get('exportacion', '01'),  # No aplica
        
        # Emisor (from vault/config)
        'emisor': {
            'rfc': SAMPLE_DATA['marco_test']['rfc'],
            'nombre': SAMPLE_DATA['marco_test']['nombre'],
            'regimen_fiscal': data.get('regimen_fiscal_emisor', '612'),  # RIF
            'fac_aeropuerto': None
        },
        
        # Receptor
        'receptor': {
            'rfc': data['rfc_receptor'],
            'nombre': data['nombre_receptor'],
            'domicilio_fiscal': data['codigo_postal'],
            'residencia_fiscal': None,
            'num_reg_id_trib': None,
            'regimen_fiscal': data.get('regimen_fiscal_receptor', '601'),  # General
            'uso_cfdi': data.get('uso_cfdi', 'G03')  # Gastos
        },
        
        # Conceptos
        'conceptos': [{
            'clave_prod_serv': data.get('clave_prod_serv', '01010101'),  # Producto genérico
            'no_identificacion': data.get('no_identificacion', ''),
            'cantidad': cantidad,
            'clave_unidad': data.get('clave_unidad', 'E48'),  # Unidad de servicio
            'unidad': data.get('unidad', 'Unidad'),
            'descripcion': data['concepto'],
            'valor_unitario': round(precio_unitario, 2),
            'importe': round(subtotal, 2),
            'descuento': 0,
            'objeto_imp': '02',  # Sí objeto de impuesto
            'impuestos': {
                'traslados': [{
                    'base': round(subtotal, 2),
                    'impuesto': '002',  # IVA
                    'tipo_factor': 'Tasa',
                    'tasa_ocuota': '0.160000',
                    'importe': round(iva, 2)
                }]
            }
        }],
        
        # Impuestos totales
        'impuestos': {
            'total_impuestos_trasladados': round(iva, 2),
            'traslados': [{
                'impuesto': '002',
                'tipo_factor': 'Tasa',
                'tasa_ocuota': '0.160000',
                'importe': round(iva, 2)
            }]
        }
    }
    
    # For demo mode, return structured data
    # In production, this would connect to SAT PAC
    return jsonify({
        'status': 'success',
        'message': 'CFDI generado (modo demo - requiere timbrado con PAC/SAT)',
        'cfdi_preview': cfdi_data,
        'totales': {
            'subtotal': round(subtotal, 2),
            'iva': round(iva, 2),
            'total': round(total, 2)
        },
        'accion_requerida': {
            'tipo': 'timbrar',
            'opciones': [
                'Usar portal gratuito del SAT',
                'Contratar PAC autorizado',
                'Integrar API de facturación'
            ]
        },
        'notas': [
            'Para timbrar gratuitamente usa: https://portalsat.plataforma.sat.gob.mx',
            'Requiere FIEL vigente',
            'El XML generado necesita firma digital y timbre del SAT'
        ]
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)