"""
Facturama PAC Integration Routes
Real CFDI emission, cancellation, and payment complements
Uses Basic Auth (username/password) per Facturama docs
"""
from flask import Blueprint, jsonify, request, send_file
import os
import logging
import io
from typing import Dict, Any

# Import the service
from facturama_service import FacturamaService

logger = logging.getLogger("facturama_routes")

# Create blueprint
facturama_bp = Blueprint('facturama', __name__)

# Initialize service
facturama_service = FacturamaService()


@facturama_bp.route('/status')
def facturama_status():
    """Check Facturama service status"""
    try:
        is_connected = facturama_service.test_connection()
        
        if is_connected:
            # Get account info
            info = facturama_service.get_account_info()
            return jsonify({
                "status": "connected",
                "mode": "sandbox" if facturama_service.is_sandbox else "production",
                "account": info.get('Name', 'Unknown'),
                "rfc": info.get('Rfc', 'Unknown'),
                "message": "Facturama service is ready"
            })
        else:
            return jsonify({
                "status": "disconnected",
                "mode": "sandbox" if facturama_service.is_sandbox else "production",
                "message": "Facturama service unavailable. Check credentials.",
                "help": "Set FACTURAMA_USERNAME and FACTURAMA_PASSWORD environment variables"
            }), 503
        
    except Exception as e:
        logger.error(f"Status check error: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@facturama_bp.route('/emitir-real', methods=['POST'])
def emitir_real():
    """
    Emit a REAL CFDI via Facturama PAC
    
    Expected JSON:
    {
        "receiver": {
            "name": "BENITOS SA DE CV",
            "rfc": "BEN123456789",
            "cfdi_use": "G03",
            "regime": "601",
            "tax_zip": "64000"
        },
        "items": [
            {
                "description": "Servicio profesional",
                "unit_price": 1000.00,
                "quantity": 1
            }
        ],
        "payment_form": "03",
        "payment_method": "PUE"
    }
    """
    data = request.json or {}
    
    try:
        # Validate required fields
        receiver_data = data.get('receiver', {})
        items = data.get('items', [])
        
        if not receiver_data or not items:
            return jsonify({
                "status": "error",
                "message": "receiver and items are required"
            }), 400
        
        if not receiver_data.get('name') or not receiver_data.get('rfc'):
            return jsonify({
                "status": "error", 
                "message": "Receiver name and RFC are required"
            }), 400
        
        # Build Facturama v2 API payload
        facturama_payload = {
            "Receiver": {
                "Name": receiver_data.get('name'),
                "Rfc": receiver_data.get('rfc').upper(),
                "CfdiUse": receiver_data.get('cfdi_use', 'G03'),
                "FiscalRegime": receiver_data.get('regime', '601'),
                "TaxZipCode": receiver_data.get('tax_zip', '64000')
            },
            "Items": [
                {
                    "ProductCode": item.get('product_code', '84111506'),
                    "Description": item.get('description', 'Servicio'),
                    "UnitCode": item.get('unit_code', 'E48'),
                    "UnitPrice": float(item.get('unit_price', 0)),
                    "Quantity": float(item.get('quantity', 1)),
                    "TaxObject": "02"  # Sí objeto de impuesto
                }
                for item in items
            ],
            "PaymentForm": data.get('payment_form', '03'),
            "PaymentMethod": data.get('payment_method', 'PUE'),
            "ExpeditionPlace": data.get('expedition_place', receiver_data.get('tax_zip', '64000')),
            "Currency": "MXN",
            "ExchangeRate": 1
        }
        
        # Emit via Facturama
        result = facturama_service.emit_cfdi(facturama_payload)
        
        if result.get('status') == 'error':
            return jsonify({
                "status": "error",
                "message": result.get('message'),
                "details": result.get('details')
            }), 400
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error emitting CFDI: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@facturama_bp.route('/cancelar-real/<cfdi_id>', methods=['DELETE'])
def cancelar_real(cfdi_id):
    """
    Cancel a REAL CFDI via Facturama
    
    Query params:
    - reason: Cancellation reason (01, 02, 03, 04)
    - uuid_replacement: Required if reason is 01
    """
    reason = request.args.get('reason', '02')
    uuid_replacement = request.args.get('uuid_replacement', '')
    
    try:
        result = facturama_service.cancel_cfdi(cfdi_id, reason, uuid_replacement)
        
        if result.get('status') == 'error':
            return jsonify({
                "status": "error",
                "message": result.get('message')
            }), 400
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error cancelling CFDI: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@facturama_bp.route('/download/<cfdi_id>/<format_type>')
def download_cfdi(cfdi_id: str, format_type: str):
    """
    Download CFDI PDF or XML
    
    format_type: 'pdf' or 'xml'
    cfdi_type: 'issued' or 'received' (from query param, default 'issued')
    """
    cfdi_type = request.args.get('type', 'issued')
    
    try:
        if format_type == 'pdf':
            content = facturama_service.download_pdf(cfdi_id, cfdi_type)
            mimetype = 'application/pdf'
            extension = 'pdf'
        elif format_type == 'xml':
            content = facturama_service.download_xml(cfdi_id, cfdi_type)
            mimetype = 'application/xml'
            extension = 'xml'
        else:
            return jsonify({
                "status": "error",
                "message": "Invalid format type. Use 'pdf' or 'xml'"
            }), 400
        
        return send_file(
            io.BytesIO(content),
            mimetype=mimetype,
            as_attachment=True,
            download_name=f"CFDI_{cfdi_id}.{extension}"
        )
        
    except Exception as e:
        logger.error(f"Error downloading CFDI: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@facturama_bp.route('/list')
def list_cfdis():
    """List emitted CFDIs from Facturama"""
    try:
        keyword = request.args.get('keyword', '')
        cfdi_type = request.args.get('type', 'issued')
        status = request.args.get('status', 'all')
        page = request.args.get('page', 1, type=int)
        
        result = facturama_service.list_cfdis(keyword, cfdi_type, status, page)
        
        if result.get('status') == 'error':
            return jsonify(result), 400
        
        return jsonify({
            "status": "success",
            "cfdis": result
        })
        
    except Exception as e:
        logger.error(f"Error listing CFDIs: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@facturama_bp.route('/detail/<cfdi_id>')
def get_cfdi_detail(cfdi_id):
    """Get CFDI detail"""
    try:
        cfdi_type = request.args.get('type', 'issued')
        result = facturama_service.get_cfdi_detail(cfdi_id, cfdi_type)
        
        if result.get('status') == 'error':
            return jsonify(result), 400
        
        return jsonify({
            "status": "success",
            "cfdi": result
        })
        
    except Exception as e:
        logger.error(f"Error getting CFDI detail: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@facturama_bp.route('/send-email', methods=['POST'])
def send_cfdi_email():
    """Send CFDI by email"""
    data = request.json or {}
    
    try:
        cfdi_id = data.get('cfdi_id')
        email = data.get('email')
        subject = data.get('subject', '')
        comments = data.get('comments', '')
        cfdi_type = data.get('type', 'issued')
        
        if not cfdi_id or not email:
            return jsonify({
                "status": "error",
                "message": "cfdi_id and email are required"
            }), 400
        
        result = facturama_service.send_cfdi_email(cfdi_id, email, subject, comments, cfdi_type)
        
        if result.get('status') == 'error':
            return jsonify(result), 400
        
        return jsonify({
            "status": "success",
            "message": "Email sent successfully"
        })
        
    except Exception as e:
        logger.error(f"Error sending email: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
