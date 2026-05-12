#!/usr/bin/env python3
"""
FiscoMind API Middleware - Connects React Mini App to Fisco Agent Daemon
Synchronous version for Flask compatibility
"""

import os
import json
import logging
from flask import Flask, jsonify, request
from flask_cors import CORS
from typing import Dict, Any
import asyncio
from threading import Thread

# Add src to path
import sys
sys.path.insert(0, '/Users/bullslab/.openclaw/agents/fisco-workspace/src')
from fisco_agent_daemon import get_agent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('FiscoAPI')

app = Flask(__name__)
CORS(app, origins="*")

# Admin wallet for simple auth check
ADMIN_WALLET = "UQDKHZ7e70CzqdvZCC83Z4WVR8POC_ZB0J1Y4zo88G-zCSRH"

# Global agent instance
agent_instance = None
agent_ready = False

def run_async(coro):
    """Run async function in sync context"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

def init_agent():
    """Initialize agent in background thread"""
    global agent_instance, agent_ready
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        agent_instance = loop.run_until_complete(get_agent())
        agent_ready = True
        logger.info("Agent initialized successfully")
    except Exception as e:
        logger.error(f"Agent initialization failed: {e}")

# Start agent initialization in background
Thread(target=init_agent, daemon=True).start()

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok", "agent_ready": agent_ready})

@app.route('/api/dashboard', methods=['GET'])
def get_dashboard():
    wallet = request.headers.get('X-Wallet')
    
    if not agent_ready:
        return jsonify({"error": "Agent still initializing"}), 503
    
    try:
        # Get fiscal data from agent
        cfdi_data = run_async(agent_instance.download_cfdis(days=30))
        deductions = run_async(agent_instance.analyze_deductions(cfdi_data.get('cfdis', [])))
        compliance = run_async(agent_instance.check_compliance())
        
        return jsonify({
            "summary": {
                "total_deductions": deductions['total_deductions'],
                "tax_savings": deductions['tax_savings_estimate'],
                "pending_alerts": compliance['urgent_count']
            },
            "cfdis": [
                {"id": "1", "issuer": "Amazon Mexico", "amount": 1200.0, "status": "Deductible"},
                {"id": "2", "issuer": "Telmex", "amount": 800.0, "status": "Deductible"},
                {"id": "3", "issuer": "Unknown Co", "amount": 300.0, "status": "Review Needed"},
            ],
            "calendar": [
                {"date": "2026-05-15", "event": "Declaración Mensual IVA"},
                {"date": "2026-05-20", "event": "Pago provisional ISR"},
            ],
            "trends": [
                {"name": "Jan", "value": 4000},
                {"name": "Feb", "value": 3000},
                {"name": "Mar", "value": 2000},
                {"name": "Apr", "value": 4500},
                {"name": "May", "value": 3800},
            ],
            "wallet": wallet
        })
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/cfdis', methods=['GET'])
def get_cfdis():
    wallet = request.headers.get('X-Wallet')
    
    if not agent_ready:
        return jsonify({"error": "Agent still initializing"}), 503
    
    try:
        cfdi_data = run_async(agent_instance.download_cfdis(days=30))
        return jsonify({
            "count": cfdi_data.get('count', 0),
            "cfdis": cfdi_data.get('cfdis', [])
        })
    except Exception as e:
        logger.error(f"CFDIs error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    if not agent_ready:
        return jsonify({"error": "Agent still initializing"}), 503
    
    try:
        compliance = run_async(agent_instance.check_compliance())
        return jsonify({
            "alerts": compliance.get('alerts', []),
            "urgent_count": compliance.get('urgent_count', 0)
        })
    except Exception as e:
        logger.error(f"Alerts error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/command', methods=['POST'])
def execute_command():
    wallet = request.headers.get('X-Wallet')
    if wallet != ADMIN_WALLET:
        return jsonify({"error": "Unauthorized - Admin only"}), 403
    
    if not agent_ready:
        return jsonify({"error": "Agent still initializing"}), 503
    
    data = request.json
    command = data.get('command')
    args = data.get('args', {})
    
    try:
        result = run_async(agent_instance.handle_command(command, args))
        return jsonify({"result": result})
    except Exception as e:
        logger.error(f"Command error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    logger.info("Starting FiscoMind API Middleware on port 5050...")
    app.run(host='0.0.0.0', port=5050, debug=False, threaded=True)
