"""
FiscoMind - Exportación de datos (Excel, CSV, PDF)
"""

import csv
import io
import json
from datetime import datetime
from typing import Dict, List
from pathlib import Path
import base64


def export_cfdis_to_csv(cfdis: List[Dict]) -> str:
    """Exporta CFDIs a CSV"""
    output = io.StringIO()
    writer = csv.writer(output)

    # Headers
    writer.writerow(
        [
            "UUID",
            "Tipo",
            "Estatus",
            "Emisor",
            "RFC Emisor",
            "Receptor",
            "RFC Receptor",
            "Monto",
            "Fecha Emisión",
            "PAC",
            "Método Pago",
            "Forma Pago",
        ]
    )

    for cfdi in cfdis:
        writer.writerow(
            [
                cfdi.get("uuid", ""),
                cfdi.get("efecto", ""),
                "Vigente" if cfdi.get("estatus") == "1" else "Cancelado",
                cfdi.get("nombre_emisor", ""),
                cfdi.get("rfc_emisor", ""),
                cfdi.get("nombre_receptor", ""),
                cfdi.get("rfc_receptor", ""),
                cfdi.get("monto", 0),
                cfdi.get("fecha_emision", ""),
                cfdi.get("pac", ""),
                cfdi.get("metodo_pago", ""),
                cfdi.get("forma_pago", ""),
            ]
        )

    return output.getvalue()


def export_resumen_to_csv(summary: Dict) -> str:
    """Exporta resumen fiscal a CSV"""
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["Concepto", "Monto"])
    writer.writerow(["Total Ingresos", summary.get("total_ingresos", 0)])
    writer.writerow(["Total Egresos", summary.get("total_egresos", 0)])
    writer.writerow(["Total Emitido", summary.get("total_emitido_monto", 0)])
    writer.writerow(["Total Deducible", summary.get("total_deducible", 0)])
    writer.writerow(["ISR Estimado", summary.get("ahorro_isr_estimado", 0)])

    return output.getvalue()


def generate_pdf_report(user_id: str, data_dir: str) -> bytes:
    """
    Genera reporte PDF con resumen fiscal.
    Requiere reportlab instalado.
    """
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
            Table,
            TableStyle,
        )
        from reportlab.lib.units import inch

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18,
        )

        # Container for elements
        elements = []
        styles = getSampleStyleSheet()

        # Title
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=24,
            textColor=colors.HexColor("#533483"),
            spaceAfter=30,
        )
        elements.append(Paragraph("FiscoMind - Reporte Fiscal", title_style))
        elements.append(Spacer(1, 0.2 * inch))

        # Date
        elements.append(
            Paragraph(
                f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                styles["Normal"],
            )
        )
        elements.append(Spacer(1, 0.3 * inch))

        # Load data
        data_dir = Path(data_dir)
        sync_files = sorted(data_dir.glob("sat_sync_*.json"), reverse=True)

        total_ingresos = 0
        total_egresos = 0
        count_vigentes = 0
        count_cancelados = 0

        for sf in sync_files:
            try:
                with open(sf) as f:
                    data = json.load(f)
                for cfdi in data.get("cfdis", []):
                    if cfdi.get("estatus") == "1":
                        count_vigentes += 1
                        if cfdi.get("efecto") == "I":
                            total_ingresos += float(cfdi.get("monto", 0))
                        elif cfdi.get("efecto") == "E":
                            total_egresos += float(cfdi.get("monto", 0))
                    else:
                        count_cancelados += 1
            except:
                continue

        # Summary table
        summary_data = [
            ["Concepto", "Valor"],
            ["Total CFDIs Vigentes", str(count_vigentes)],
            ["Total CFDIs Cancelados", str(count_cancelados)],
            ["Total Ingresos", f"${total_ingresos:,.2f}"],
            ["Total Egresos", f"${total_egresos:,.2f}"],
            [
                "ISR Estimado (30%)",
                f"${max(0, total_ingresos - total_egresos) * 0.30:,.2f}",
            ],
        ]

        summary_table = Table(summary_data, colWidths=[3 * inch, 2 * inch])
        summary_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#533483")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 14),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ]
            )
        )
        elements.append(summary_table)

        elements.append(Spacer(1, 0.5 * inch))

        # Disclaimer
        disclaimer = Paragraph(
            "<i>Este reporte es generado automáticamente por FiscoMind. "
            "Consulta con tu contador para la declaración oficial.</i>",
            styles["Normal"],
        )
        elements.append(disclaimer)

        # Build PDF
        doc.build(elements)
        pdf = buffer.getvalue()
        buffer.close()

        return pdf

    except ImportError:
        # Fallback si reportlab no está instalado
        return b"PDF generation not available. Install reportlab."
    except Exception as e:
        return f"Error generating PDF: {str(e)}".encode()


class ExportManager:
    """Manager para exportaciones de FiscoMind"""

    def __init__(self, data_dir: str = "/app/data"):
        self.data_dir = Path(data_dir)

    def export_all(self, user_id: str = "marco_test") -> Dict:
        """
        Exporta todos los datos del usuario en múltiples formatos.
        """
        user_dir = self.data_dir / "users" / user_id

        # Load CFDIs
        cfdis = []
        sync_files = sorted(user_dir.glob("sat_sync_*.json"), reverse=True)
        for sf in sync_files:
            try:
                with open(sf) as f:
                    data = json.load(f)
                cfdis.extend(data.get("cfdis", []))
            except:
                continue

        # Generate exports
        csv_data = export_cfdis_to_csv(cfdis)
        pdf_data = generate_pdf_report(user_id, str(user_dir))

        return {
            "status": "success",
            "csv": base64.b64encode(csv_data.encode()).decode(),
            "pdf": base64.b64encode(pdf_data).decode()
            if isinstance(pdf_data, bytes)
            else None,
            "total_cfdis": len(cfdis),
            "generated_at": datetime.now().isoformat(),
        }
