"""
Facturama PAC Integration Routes
Real CFDI emission, cancellation, and payment complements
"""
from flask import Blueprint, jsonify, request
import os
import logging
from typing import Dict, Any

# Import the service
from facturama_service import FacturamaService

logger = logging.getLogger("facturama_routes")

# Create blueprint
facturama_bp = Blueprint('facturama', __name__)

# Initialize service
facturama_service = FacturamaService()


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
        "payment_form": "03",  // Transferencia
        "payment_method": "PUE", // Pago único o PPD
        "serie": "A",
        "folio": "1"
    }
    """
    data = request.json or {}
    
    try:
        # Transform data to Facturama format
        receiver_data = data.get('receiver', {})
        items = data.get('items', [])
        
        if not receiver_data or not items:
            return jsonify({
                "status": "error",
                "message": "receiver and items are required"
            }), 400
        
        # Build Facturama payload
        facturama_payload = {
            "Receiver": {
                "Name": receiver_data.get('name'),
                "Rfc": receiver_data.get('rfc'),
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
                    "Subtotal": float(item.get('unit_price', 0)) * float(item.get('quantity', 1)),
                    "TaxObject": "02"
                }
                for item in items
            ],
            "PaymentForm": data.get('payment_form', '03'),
            "PaymentMethod": data.get('payment_method', 'PUE'),
            "ExpeditionPlace": data.get('expedition_place', '64000'),
            "Currency": "MXN",
            "ExchangeRate": 1,
            "Serie": data.get('serie', ''),
            "Folio": data.get('folio', '')
        }
        
        # Emit via Facturama
        result = facturama_service.emit_cfdi(facturama_payload)
        
        if result.get('status') == 'error':
            return jsonify({
                "status": "error",
                "message": result.get('message'),
                "details": result.get('details')
            }), 400
        
        return jsonify({
            "status": "success",
            "message": "CFDI emitido correctamente",
            "cfdi": {
                "id": result.get('Id'),
                "uuid": result.get('Complement', {}).get('TaxStamp', {}).get('Uuid'),
                "cfdi_type": result.get('CfdiType'),
                "total": result.get('Total'),
                "status": result.get('Status'),
                "pdf_url": f"/facturama/download/{result.get('Id')}/pdf",
                "xml_url": f"/facturama/download/{result.get('Id')}/xml",
                "qr_code": result.get('Complement', {}).get('TaxStamp', {}).get('QrCode'),
                "date": result.get('Date'),
                "original_string": result.get('OriginalString')
            }
        })
        
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
    """
    reason = request.args.get('reason', '02')
    
    try:
        result = facturama_service.cancel_cfdi(cfdi_id, reason)
        
        if result.get('status') == 'error':
            return jsonify({
                "status": "error",
                "message": result.get('message')
            }), 400
        
        return jsonify({
            "status": "success",
            "message": "CFDI cancelado correctamente",
            "cancelled_cfdi": cfdi_id,
            "uuid": result.get('Uuid'),
            "acknowledgment": result.get('Acuse')
        })
        
    except Exception as e:
        logger.error(f"Error cancelling CFDI: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@facturama_bp.route('/complemento-pago-real', methods=['POST'])
def complemento_pago_real():
    """
    Emit a REAL Complemento de Pago via Facturama
    
    Expected JSON:
    {
        "receiver": {
            "name": "BENITOS SA DE CV",
            "rfc": "BEN123456789",
            "tax_zip": "64000"
        },
        "payment_date": "2024-01-15",
        "payment_form": "03",  // Transferencia
        "amount": 10000.00,
        "related_documents": [
            {
                "uuid": "...",  // UUID of original invoice
                "payment_method": "PPD",
                "partiality_number": 1,
                "previous_amount": 20000.00,
                "amount_paid": 10000.00,
                "outstanding_balance": 10000.00
            }
        ]
    }
    """
    data = request.json or {}
    
    try:
        receiver = data.get('receiver', {})
        related_docs = data.get('related_documents', [])
        
        if not receiver or not related_docs:
            return jsonify({
                "status": "error",
                "message": "receiver and related_documents are required"
            }), 400
        
        # Build Facturama payload for complemento de pago
        facturama_payload = {
            "CfdiType": "P",
            "Receiver": {
                "Name": receiver.get('name'),
                "Rfc": receiver.get('rfc'),
                "CfdiUse": "CP01",
                "FiscalRegime": receiver.get('regime', '601'),
                "TaxZipCode": receiver.get('tax_zip', '64000')
            },
            "PaymentForm": data.get('payment_form', '03'),
            "PaymentMethod": "PUE",  // Payment receipts are always PUE
            "ExpeditionPlace": data.get('expedition_place', '64000'),
            "Currency": "MXN",
            "ExchangeRate": 1,
            "RelatedDocuments": [
                {
                    "Uuid": doc.get('uuid'),
                    "PaymentMethod": doc.get('payment_method', 'PPD'),
                    "PartialityNumber": doc.get('partiality_number', 1),
                    "PreviousAmount": float(doc.get('previous_amount', 0)),
                    "AmountPaid": float(doc.get('amount_paid', 0)),
                    "OutstandingBalance": float(doc.get('outstanding_balance', 0))
                }
                for doc in related_docs
            ]
        }
        
        result = facturama_service.emit_cfdi(facturama_payload)
        
        if result.get('status') == 'error':
            return jsonify({
                "status": "error",
                "message": result.get('message'),
                "details": result.get('details')
            }), 400
        
        return jsonify({
            "status": "success",
            "message": "Complemento de pago emitido correctamente",
            "complemento": {
                "id": result.get('Id'),
                "uuid": result.get('Complement', {}).get('TaxStamp', {}).get('Uuid'),
                "type": "P",
                "total": result.get('Total'),
                "date": result.get('Date'),
                "pdf_url": f"/facturama/download/{result.get('Id')}/pdf",
                "xml_url": f"/facturama/download/{result.get('Id')}/xml",
                "qr_code": result.get('Complement', {}).get('TaxStamp', {}).get('QrCode'),
                "related_documents": related_docs
            }
        })
        
    except Exception as e:
        logger.error(f"Error emitting complemento de pago: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@facturama_bp.route('/download/<cfdi_id>/<format_type>')
def download_cfdi(cfdi_id: str, format_type: str):
    """
    Download CFDI PDF or XML
    
    format_type: 'pdf' or 'xml'
    """
    try:
        if format_type == 'pdf':
            content = facturama_service.download_pdf(cfdi_id)
            mimetype = 'application/pdf'
            extension = 'pdf'
        elif format_type == 'xml':
            content = facturama_service.download_xml(cfdi_id)
            mimetype = 'application/xml'
            extension = 'xml'
        else:
            return jsonify({
                "status": "error",
                "message": "Invalid format type. Use 'pdf' or 'xml'"
            }), 400
        
        from flask import send_file
        import io
        
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
        rfcs = request.args.getlist('rfc')
        result = facturama_service.list_cfdis(rfcs if rfcs else None)
        
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


@facturama_bp.route('/status')
def facturama_status():
    """Check Facturama service status"""
    try:
        from facturama_service import test_connection
        is_connected = test_connection()
        
        return jsonify({
            "status": "connected" if is_connected else "disconnected",
            "mode": "sandbox" if os.environ.get('FACTURAMA_SANDBOX', 'true').lower() == 'true' else "production",
            "message": "Facturama service is ready" if is_connected else "Facturama service unavailable"
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
