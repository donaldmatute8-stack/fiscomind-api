"""
FiscoMind - Exportación de datos (Excel, CSV, PDF)
"""

import csv
import io
import json
from datetime import datetime
from pathlib import Path


def export_cfdis_to_csv(cfdis: list) -> str:
    """Exporta CFDIs a CSV"""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "UUID",
            "Tipo",
            "Estatus",
            "Emisor",
            "RFC_Emisor",
            "Receptor",
            "RFC_Receptor",
            "Monto",
            "Fecha Emisión",
            "Método Pago",
            "Forma Pago",
            "Uso CFDI",
        ]
    )
    for c in cfdis:
        writer.writerow(
            [
                c.get("uuid", ""),
                {"I": "Ingreso", "E": "Egreso", "P": "Pago"}.get(
                    c.get("efecto"), c.get("efecto", "")
                ),
                "Vigente" if c.get("estatus") == "1" else "Cancelado",
                c.get("nombre_emisor", ""),
                c.get("rfc_emisor", ""),
                c.get("nombre_receptor", ""),
                c.get("rfc_receptor", ""),
                c.get("monto", 0),
                c.get("fecha_emision", ""),
                c.get("metodo_pago", ""),
                c.get("forma_pago", ""),
                c.get("uso_cfdi", ""),
            ]
        )
    return output.getvalue()


def generate_pdf_report(
    user_id: str, cfdis: list = None, data_dir: str = "/app/data"
) -> bytes:
    """
    Genera reporte PDF con resumen fiscal. Si se pasa `cfdis`, los usa directamente.
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

        if cfdis is None:
            # fallback legacy
            cfdis = []
            user_dir = Path(data_dir) / "users" / user_id
            for sf in sorted(user_dir.glob("sat_sync_*.json"), reverse=True)[:5]:
                try:
                    with open(sf) as f:
                        data = json.load(f)
                    cfdis.extend(data.get("cfdis", []))
                except:
                    continue

        total_ingresos = sum(
            float(c.get("monto", 0))
            for c in cfdis
            if c.get("efecto") in ("I", "ingreso")
        )
        total_egresos = sum(
            float(c.get("monto", 0))
            for c in cfdis
            if c.get("efecto") in ("E", "egreso")
        )
        count_vigentes = sum(1 for c in cfdis if c.get("estatus") == "1")
        count_cancelados = sum(1 for c in cfdis if c.get("estatus") != "1")
        total_monto = total_ingresos
        deducciones = sum(
            float(c.get("monto", 0))
            for c in cfdis
            if c.get("uso_cfdi", "S01") in ("G03", "G01", "I04", "I06")
        )

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18,
        )
        elements = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "FiscoMindTitle",
            parent=styles["Heading1"],
            fontSize=22,
            textColor=colors.HexColor("#533483"),
            spaceAfter=20,
        )
        elements.append(Paragraph("FiscoMind — Reporte Fiscal", title_style))
        elements.append(
            Paragraph(
                f"RFC: {user_id}  |  Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                styles["Normal"],
            )
        )
        elements.append(Spacer(1, 0.4 * inch))

        summary_data = [
            ["Concepto", "Valor"],
            ["CFDIs Vigentes", str(count_vigentes)],
            ["CFDIs Cancelados", str(count_cancelados)],
            ["Total Ingresos", f"${total_ingresos:,.2f}"],
            ["Total Egresos", f"${total_egresos:,.2f}"],
            ["Deducciones Estimadas", f"${deducciones:,.2f}"],
            ["ISR Estimado (30%)", f"${max(0, total_monto - deducciones) * 0.30:,.2f}"],
        ]
        table = Table(summary_data, colWidths=[3 * inch, 2 * inch])
        table.setStyle(
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
        elements.append(table)
        elements.append(Spacer(1, 0.3 * inch))
        elements.append(
            Paragraph(
                "<i>Este reporte es generado automáticamente por FiscoMind. "
                "Consulta con tu contador para la declaración oficial.</i>",
                styles["Normal"],
            )
        )
        doc.build(elements)
        return buffer.getvalue()
    except ImportError:
        return b""
    except Exception as e:
        return f"Error: {e}".encode()
