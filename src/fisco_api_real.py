#!/usr/bin/env python3
"""
FiscoMind API - Real Data Connector
Serves actual CFDI data from SAT to the React Mini App
"""

import os
import json
import logging
from flask import Flask, jsonify, request
from flask_cors import CORS
from typing import Dict, Any
from datetime import datetime, timedelta

# Import real SAT connector
from sat_connector_real import SATConnectorReal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('FiscoAPI-Real')

app = Flask(__name__)
CORS(app, origins="*")

# In-memory cache for user data
user_cache: Dict[str, Dict] = {}

# RFC of the user
USER_RFC = "MUTM8610091NA"


def get_or_create_connector():
    """Get or create SAT connector"""
    return SATConnectorReal(rfc=USER_RFC)


def calculate_deductions(cfdis: list) -> Dict[str, Any]:
    """Calculate total deductions and tax savings from CFDIs"""
    total_deductions = 0.0
    tax_rate = 0.30  # Approximate Mexican tax rate
    
    for cfdi in cfdis:
        if cfdi.get('deductible', False):
            total_deductions += cfdi.get('monto', 0)
    
    return {
        'total_deductions': total_deductions,
        'tax_savings': total_deductions * tax_rate
    }


def get_fiscal_calendar() -> list:
    """Get upcoming fiscal obligations"""
    today = datetime.now()
    calendar = []
    
    # Next monthly declaration (17th of current or next month)
    if today.day < 17:
        next_monthly = today.replace(day=17)
    else:
        if today.month == 12:
            next_monthly = today.replace(year=today.year + 1, month=1, day=17)
        else:
            next_monthly = today.replace(month=today.month + 1, day=17)
    
    calendar.append({
        'date': next_monthly.strftime('%Y-%m-%d'),
        'event': 'Declaración Mensual IVA/ISR',
        'urgent': (next_monthly - today).days <= 5
    })
    
    # Annual declaration (April)
    annual = today.replace(month=4, day=30)
    if today > annual:
        annual = annual.replace(year=today.year + 1)
    
    calendar.append({
        'date': annual.strftime('%Y-%m-%d'),
        'event': 'Declaración Anual Persona Física',
        'urgent': False
    })
    
    return calendar


@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "ok",
        "version": "2.0-real",
        "rfc": USER_RFC
    })


@app.route('/api/dashboard', methods=['GET'])
def get_dashboard():
    """Get real dashboard data from SAT"""
    wallet = request.headers.get('X-Wallet', 'anonymous')
    
    try:
        connector = get_or_create_connector()
        
        # Download recent CFDIs
        today = datetime.now()
        thirty_days_ago = today - timedelta(days=30)
        
        cfdis = connector.download_cfdis(
            date_start=thirty_days_ago.strftime('%Y-%m-%d'),
            date_end=today.strftime('%Y-%m-%d'),
            tipo="recibidos"
        )
        
        # Calculate deductions
        deductions = calculate_deductions(cfdis)
        
        # Get compliance
        compliance = connector.get_compliance_opinion()
        
        # Get calendar
        calendar = get_fiscal_calendar()
        
        # Format recent CFDIs
        recent_cfdis = []
        for cfdi in cfdis[:5]:  # Last 5
            recent_cfdis.append({
                'id': cfdi.get('folio', 'N/A'),
                'issuer': cfdi.get('emisor', 'Unknown'),
                'amount': cfdi.get('monto', 0),
                'status': 'Deductible' if cfdi.get('deductible') else 'No deducible',
                'date': cfdi.get('fecha', ''),
                'rfc': cfdi.get('emisor_rfc', '')
            })
        
        # Pending alerts
        pending_alerts = len([c for c in calendar if c.get('urgent')])
        
        # Generate trends (mock based on deductions)
        trends = [
            {'name': 'Ene', 'value': deductions['total_deductions'] * 0.6},
            {'name': 'Feb', 'value': deductions['total_deductions'] * 0.7},
            {'name': 'Mar', 'value': deductions['total_deductions'] * 0.8},
            {'name': 'Abr', 'value': deductions['total_deductions'] * 0.9},
            {'name': 'May', 'value': deductions['total_deductions']},
        ]
        
        response = {
            "summary": {
                "total_deductions": round(deductions['total_deductions'], 2),
                "tax_savings": round(deductions['tax_savings'], 2),
                "pending_alerts": pending_alerts
            },
            "cfdis": recent_cfdis,
            "calendar": calendar,
            "trends": trends,
            "compliance": compliance['status'],
            "wallet": wallet,
            "last_updated": datetime.now().isoformat()
        }
        
        # Cache for user
        user_cache[wallet] = response
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/cfdis', methods=['GET'])
def get_cfdis():
    """Get all CFDIs"""
    wallet = request.headers.get('X-Wallet', 'anonymous')
    
    try:
        connector = get_or_create_connector()
        
        # Get date range from query params
        days = int(request.args.get('days', 30))
        today = datetime.now()
        start = today - timedelta(days=days)
        
        cfdis = connector.download_cfdis(
            date_start=start.strftime('%Y-%m-%d'),
            date_end=today.strftime('%Y-%m-%d'),
            tipo="recibidos"
        )
        
        return jsonify({
            "count": len(cfdis),
            "rfc": USER_RFC,
            "cfdis": cfdis
        })
        
    except Exception as e:
        logger.error(f"CFDIs error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/compliance', methods=['GET'])
def get_compliance():
    """Get compliance opinion"""
    try:
        connector = get_or_create_connector()
        opinion = connector.get_compliance_opinion()
        
        return jsonify(opinion)
        
    except Exception as e:
        logger.error(f"Compliance error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/refresh', methods=['POST'])
def refresh_data():
    """Force refresh of SAT data"""
    wallet = request.headers.get('X-Wallet', 'anonymous')
    
    # Clear cache for this user
    if wallet in user_cache:
        del user_cache[wallet]
    
    return jsonify({"status": "Cache cleared. Data will refresh on next request."})


if __name__ == '__main__':
    logger.info("🚀 Starting FiscoMind REAL API on port 5050...")
    logger.info(f"   RFC: {USER_RFC}")
    logger.info("   Using real SAT connection with satcfdi")
    app.run(host='0.0.0.0', port=5050, debug=False, threaded=True)
