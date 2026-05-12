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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)