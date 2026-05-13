"""
FiscoMind - Motor de Regularización Fiscal
Genera planes de regularización basados en datos reales del SAT.
Analiza: prescripción, declaraciones en ceros, suspensión, baja.
"""

import json
import io
from datetime import date, timedelta, datetime
from pathlib import Path
from typing import Dict, List, Tuple
from collections import defaultdict

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

    HAS_PDF = True
except ImportError:
    HAS_PDF = False

# ─── Constantes SAT ────────────────────────────────────────────────

PRESCRIPCION_NORMAL = 5  # años (Art. 146 CFF)
PRESCRIPCION_DEFRAUDACION = 7  # años si hay defraudación fiscal
FECHA_LIMITE_PRESCRIPCION_2022 = date(2022, 1, 1)

# Años clave para Marco (desde 2022)
AÑOS_RELEVANTES = [2022, 2023, 2024, 2025, 2026]

# Plazos de declaración (días del mes)
PLAZOS_MENSUALES = {
    "ISR": 17,
    "IVA": 17,
    "IEPS": 17,
    "RETENCIONES": 17,
}

# Multas (Art. 75, 76, 77 CFF)
MULTA_NO_PRESENTAR = 0.015  # 1.5% del impuesto por cada mes de retraso
MULTA_CORRECCION = 0.005  # 0.5% si presentas corrección voluntaria
MULTA_DECLARACION_EXTEMPORANEA = 1083  # UMAs aprox (~$108,300 MXN max)


class RegularizacionEngine:
    """
    Motor inteligente de regularización fiscal.
    Analiza CFDIs detectados vs. obligaciones esperadas.
    """

    def __init__(self, rfc: str, data_dir: str = "/app/data"):
        self.rfc = rfc
        self.data_dir = Path(data_dir)
        self.plan = {}
        self.riesgo = "desconocido"
        self.recomendacion_principal = ""
        self.periodos_pendientes = []

    def _load_cfdis(self) -> List[Dict]:
        cache_file = self.data_dir / "cfdi_cache.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text())
                return data.get("recibidos", []) + data.get("emitidos", [])
            except:
                pass
        return []

    def _detectar_periodos_con_ingresos(self, cfdis: List[Dict]) -> Dict[str, float]:
        """Agrupa CFDIs por mes fiscal y suma ingresos."""
        periodos = defaultdict(float)
        for c in cfdis:
            if c.get("estatus") != "1":
                continue  # ignorar cancelados
            fecha = c.get("fecha_emision", "")
            if len(fecha) >= 7:
                mes_fiscal = fecha[:7]  # YYYY-MM
                if c.get("efecto") in ("I", "ingreso"):
                    periodos[mes_fiscal] += float(c.get("monto", 0))
        return dict(periodos)

    def _detectar_periodos_con_egresos(self, cfdis: List[Dict]) -> Dict[str, float]:
        periodos = defaultdict(float)
        for c in cfdis:
            if c.get("estatus") != "1":
                continue
            fecha = c.get("fecha_emision", "")
            if len(fecha) >= 7:
                mes_fiscal = fecha[:7]
                if c.get("efecto") in ("E", "egreso"):
                    periodos[mes_fiscal] += float(c.get("monto", 0))
        return dict(periodos)

    def _calcular_obligaciones_esperadas(self) -> List[Dict]:
        """
        Calcula todas las declaraciones mensuales esperadas desde 2022 hasta hoy.
        """
        obligaciones = []
        hoy = date.today()
        inicio = date(2022, 1, 1)

        # Generar todos los meses desde 2022 hasta ahora
        año, mes = inicio.year, inicio.month
        while (año, mes) <= (hoy.year, hoy.month):
            periodo = f"{año}-{str(mes).zfill(2)}"
            vence = date(año, mes, 17) + timedelta(days=30)  # plazo aprox
            dias_retraso = (hoy - vence).days if vence < hoy else 0

            obligaciones.append(
                {
                    "periodo": periodo,
                    "año": año,
                    "mes": mes,
                    "tipo": "mensual",
                    "vencimiento": vence.isoformat(),
                    "dias_retraso": max(0, dias_retraso),
                    "declarada": None,  # desconocido
                    "estimado_rezago": dias_retraso > 0
                    and dias_retraso > 45,  # si pasó más de 45 días
                }
            )

            mes += 1
            if mes > 12:
                mes = 1
                año += 1

        return obligaciones

    def analizar(self, cfdis: List[Dict] = None) -> Dict:
        if cfdis is None:
            cfdis = self._load_cfdis()

        ingresos_mensuales = self._detectar_periodos_con_ingresos(cfdis)
        egresos_mensuales = self._detectar_periodos_con_egresos(cfdis)
        obligaciones = self._calcular_obligaciones_esperadas()

        # Cruce: ¿qué meses tienen ingresos pero no consta declaración?
        meses_con_actividad = set(ingresos_mensuales.keys())
        meses_sin_actividad = (
            set(o["periodo"] for o in obligaciones) - meses_con_actividad
        )
        total_periodos_esperados = len(obligaciones)
        periodos_con_ingresos = len(meses_con_actividad)
        periodos_sin_ingresos = len(meses_sin_actividad)

        # Ingresos totales detectados
        total_ingresos = sum(ingresos_mensuales.values())
        total_egresos = sum(egresos_mensuales.values())

        # ISR estimado por año
        isr_por_año = {}
        for año in AÑOS_RELEVANTES:
            ing_año = sum(
                v for k, v in ingresos_mensuales.items() if k.startswith(str(año))
            )
            egr_año = sum(
                v for k, v in egresos_mensuales.items() if k.startswith(str(año))
            )
            isr_por_año[año] = {
                "ingresos": round(ing_año, 2),
                "egresos": round(egr_año, 2),
                "base": round(max(0, ing_año - egr_año), 2),
                "isr_estimado": round(max(0, ing_año - egr_año) * 0.30, 2),
            }

        # Determinar riesgo
        if total_ingresos == 0:
            self.riesgo = "BAJO"
            self.recomendacion_principal = (
                "SUSPENSIÓN TEMPORAL + declarar en ceros 2022-2025"
            )
        elif total_ingresos < 400000:  # < $400k año
            self.riesgo = "MEDIO"
            self.recomendacion_principal = "Declarar ceros en meses sin actividad, normal en meses con ingresos, considerar suspensión"
        else:
            self.riesgo = "ALTO"
            self.recomendacion_principal = (
                "Regularización formal obligatoria - asesoría profesional recomendada"
            )

        # ¿Qué declarar en ceros?
        periodos_ceros = [
            o
            for o in obligaciones
            if o["periodo"] in meses_sin_actividad and o["dias_retraso"] > 45
        ]  # solo los rezagados

        # ¿Qué declarar normal?
        periodos_normal = [
            o for o in obligaciones if o["periodo"] in meses_con_actividad
        ]

        # Prescripción: períodos anteriores a 2021 ya prescribieron (5 años)
        hoy = date.today()
        fecha_prescripcion = date(hoy.year - 5, hoy.month, hoy.day)
        periodos_prescritos = [
            o for o in obligaciones if date(o["año"], o["mes"], 1) < fecha_prescripcion
        ]

        self.plan = {
            "rfc": self.rfc,
            "fecha_analisis": hoy.isoformat(),
            "riesgo": self.riesgo,
            "recomendacion_principal": self.recomendacion_principal,
            "totales": {
                "periodos_esperados": total_periodos_esperados,
                "periodos_con_ingresos": periodos_con_ingresos,
                "periodos_sin_ingresos": periodos_sin_ingresos,
                "total_ingresos_detectados": round(total_ingresos, 2),
                "total_egresos_detectados": round(total_egresos, 2),
                "isr_estimado_total": round(
                    sum(a["isr_estimado"] for a in isr_por_año.values()), 2
                ),
            },
            "por_año": isr_por_año,
            "estrategia": {
                "periodos_a_declarar_ceros": len(periodos_ceros),
                "periodos_a_declarar_normal": len(periodos_normal),
                "periodos_prescritos_no_necesarios": len(periodos_prescritos),
                "lista_ceros": [o["periodo"] for o in periodos_ceros[:12]],  # max 12
                "lista_normal": [o["periodo"] for o in periodos_normal[:12]],
                "prescritos": [o["periodo"] for o in periodos_prescritos[:12]],
            },
            "costos_estimados": {
                "multas_por_no_presentar": len(periodos_ceros) * MULTA_NO_PRESENTAR,
                "multas_por_correccion": len(periodos_normal) * MULTA_CORRECCION,
                "isr_total_estimado": round(
                    sum(a["isr_estimado"] for a in isr_por_año.values()), 2
                ),
                "total_a_pagar_estimado": round(
                    sum(a["isr_estimado"] for a in isr_por_año.values())
                    + len(periodos_ceros)
                    * MULTA_NO_PRESENTAR
                    * 5000,  # placeholder para multa real
                    2,
                ),
            },
            "pasos": self._generar_pasos(
                periodos_ceros, periodos_normal, periodos_prescritos
            ),
        }

        return self.plan

    def _generar_pasos(self, ceros, normal, prescritos) -> List[Dict]:
        pasos = []
        hoy = date.today()

        # 1. Verificar prescripción
        pasos.append(
            {
                "orden": 1,
                "titulo": "Verificar prescripción",
                "descripcion": f"Los períodos anteriores a {(hoy.year - 5)}-{(str(hoy.month).zfill(2))} ya prescribieron. NO es necesario declarar.",
                "periodos_afectados": [p["periodo"] for p in prescritos[:5]]
                or ["Ninguno relevante"],
                "accion": "Omitir declaraciones prescritas",
            }
        )

        # 2. Declarar ceros en períodos sin actividad
        if ceros:
            pasos.append(
                {
                    "orden": 2,
                    "titulo": "Declarar en ceros",
                    "descripcion": f"Presentar {len(ceros)} declaraciones en ceros por meses sin actividad económica.",
                    "periodos_afectados": [c["periodo"] for c in ceros[:12]],
                    "accion": "Portal SAT → Declaraciones en Ceros (automático)",
                    "costo": "$0 ISR + multas mínimas",
                }
            )

        # 3. Declarar normal si hay ingresos
        if normal:
            pasos.append(
                {
                    "orden": 3,
                    "titulo": "Declarar con datos reales",
                    "descripcion": f"Presentar {len(normal)} declaraciones con ingresos/egresos detectados.",
                    "periodos_afectados": [n["periodo"] for n in normal[:12]],
                    "accion": "Usar FiscoMind para generar borrador → capturar en SAT",
                    "costo": "ISR según tabla + multa 0.5%",
                }
            )

        # 4. Suspensión temporal
        pasos.append(
            {
                "orden": 4,
                "titulo": "Suspensión Temporal (recomendada)",
                "descripcion": "Si no vas a facturar por 6+ meses, suspender actividades evita futuras obligaciones.",
                "periodos_afectados": ["Futuros"],
                "accion": "SAT → Mi Portal → Suspensión de Actividades",
                "costo": "$0",
            }
        )

        # 5. Guardar acuses
        pasos.append(
            {
                "orden": 5,
                "titulo": "Guardar todos los acuses",
                "descripcion": "Descargar y respaldar cada acuse de presentación. Son tu constancia legal de cumplimiento.",
                "accion": "Crear carpeta /FiscoMind/Acuses/[AÑO]/",
                "costo": "$0",
            }
        )

        return pasos

    def generar_pdf(self) -> bytes:
        if not HAS_PDF:
            return b"PDF generation not available: reportlab not installed"

        data = self.analizar()
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
        title = ParagraphStyle(
            "RegTitle",
            parent=styles["Heading1"],
            fontSize=22,
            textColor=colors.HexColor("#533483"),
            spaceAfter=20,
        )
        subtitle = ParagraphStyle(
            "RegSub",
            parent=styles["Heading2"],
            fontSize=16,
            textColor=colors.HexColor("#8B5CF6"),
            spaceAfter=12,
        )

        # Header
        elements.append(Paragraph("FiscoMind — Plan de Regularización Fiscal", title))
        elements.append(
            Paragraph(
                f"RFC: {self.rfc}  |  Fecha: {date.today().isoformat()}",
                styles["Normal"],
            )
        )
        elements.append(Spacer(1, 0.2 * inch))

        # Riesgo
        color_riesgo = {"BAJO": "#22c55e", "MEDIO": "#f59e0b", "ALTO": "#ef4444"}.get(
            data["riesgo"], "#666"
        )
        elements.append(
            Paragraph(
                f"Riesgo actual: <b>{data['riesgo']}</b>",
                ParagraphStyle(
                    "Riesgo",
                    parent=styles["Normal"],
                    textColor=colors.HexColor(color_riesgo),
                    fontSize=14,
                ),
            )
        )
        elements.append(Spacer(1, 0.15 * inch))

        # Resumen
        elements.append(Paragraph("📊 Resumen de Obligaciones", subtitle))
        resumen = [
            ["Concepto", "Cantidad", "Estimado"],
            ["Períodos esperados", str(data["totales"]["periodos_esperados"]), ""],
            [
                "Con ingresos detectados",
                str(data["totales"]["periodos_con_ingresos"]),
                f"${data['totales']['total_ingresos_detectados']:,.2f}",
            ],
            [
                "Sin ingresos",
                str(data["totales"]["periodos_sin_ingresos"]),
                "Declarar en ceros",
            ],
            [
                "ISR estimado total",
                "",
                f"${data['totales']['isr_estimado_total']:,.2f}",
            ],
        ]
        t = Table(resumen, colWidths=[2.8 * inch, 1.5 * inch, 1.7 * inch])
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#533483")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                ]
            )
        )
        elements.append(t)
        elements.append(Spacer(1, 0.3 * inch))

        # Por año
        elements.append(Paragraph("📅 Análisis por Año", subtitle))
        año_data = [["Año", "Ingresos", "Egresos", "ISR Est."]]
        for año, vals in data["por_año"].items():
            año_data.append(
                [
                    str(año),
                    f"${vals['ingresos']:,.2f}",
                    f"${vals['egresos']:,.2f}",
                    f"${vals['isr_estimado']:,.2f}",
                ]
            )
        t2 = Table(año_data, colWidths=[1.5 * inch, 1.5 * inch, 1.5 * inch, 1.5 * inch])
        t2.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#8B5CF6")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ]
            )
        )
        elements.append(t2)
        elements.append(Spacer(1, 0.3 * inch))

        # Pasos
        elements.append(Paragraph("✅ Plan de Acción Recomendado", subtitle))
        for paso in data["pasos"]:
            elements.append(
                Paragraph(
                    f"<b>{paso['orden']}. {paso['titulo']}</b>", styles["Heading3"]
                )
            )
            elements.append(Paragraph(f"{paso['descripcion']}", styles["Normal"]))
            elements.append(
                Paragraph(f"<i>Acción: {paso['accion']}</i>", styles["Italic"])
            )
            if paso.get("costo"):
                elements.append(Paragraph(f"Costo: {paso['costo']}", styles["Normal"]))
            elements.append(Spacer(1, 0.1 * inch))

        # Advertencia legal
        elements.append(Spacer(1, 0.2 * inch))
        elements.append(
            Paragraph(
                "<b>⚠️ ADVERTENCIA LEGAL:</b> Este plan es generado por FiscoMind basado en los CFDIs disponibles. "
                "Los cálculos son estimados. Para montos significativos o situaciones complejas, "
                "consultar con un contador público registrado ante el SAT. "
                "La prescripción fiscal requiere que el SAT no haya iniciado acciones de fiscalización.",
                styles["Normal"],
            )
        )

        doc.build(elements)
        return buffer.getvalue()


def generar_plan_regularizacion(rfc: str, data_dir: str = "/app/data") -> Dict:
    """Entry point rápido."""
    engine = RegularizacionEngine(rfc=rfc, data_dir=data_dir)
    return engine.analizar()


def generar_pdf_regularizacion(rfc: str, data_dir: str = "/app/data") -> bytes:
    engine = RegularizacionEngine(rfc=rfc, data_dir=data_dir)
    return engine.generar_pdf()
