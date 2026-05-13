"""
FiscoMind - Consultoría Fiscal SAT 2026
Asistente de estrategias fiscales basado en normativas vigentes.
"""

import os
import json
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional
from pathlib import Path


class SAT2026Consultant:
    """
    Consultor fiscal basado en normativas SAT 2026.
    Da recomendaciones personalizadas para reducir ISR legalmente.
    """

    # Normativas SAT 2026
    LIMITES_2026 = {
        "deduccion_colegiaturas": 16980.00,
        "pago_efectivo_max": 2000.00,
        "rif_ingresos_max": 3500000.00,
    }

    # Tarifas ISR 2026 (Personas Físicas)
    TARIFAS_ISR = [
        {"limite": 89544.00, "tasa": 0.0194, "cuota_fija": 0},
        {"limite": 127060.00, "tasa": 0.0640, "cuota_fija": 1714},
        {"limite": 296380.00, "tasa": 0.1088, "cuota_fija": 12629},
        {"limite": 564170.00, "tasa": 0.1600, "cuota_fija": 45264},
        {"limite": 752240.00, "tasa": 0.1792, "cuota_fija": 107144},
        {"limite": 2256720.00, "tasa": 0.2136, "cuota_fija": 140936},
        {"limite": float("inf"), "tasa": 0.3000, "cuota_fija": 460737},
    ]

    def __init__(self, data_dir: str = "/app/data/users/marco_test"):
        self.data_dir = Path(data_dir)

    def _load_cfdis(self) -> List[Dict]:
        """Carga CFDIs del usuario"""
        cfdis = []
        sync_files = sorted(self.data_dir.glob("sat_sync_*.json"), reverse=True)
        for sf in sync_files:
            try:
                with open(sf) as f:
                    data = json.load(f)
                cfdis.extend(data.get("cfdis", []))
            except:
                continue
        return cfdis

    def analyze_declarations(self) -> Dict:
        """
        Analiza estado de declaraciones y detecta rezago.
        """
        result = {
            "status": "success",
            "declaraciones_pendientes": [],
            "riesgos_detectados": [],
            "recomendaciones": [],
        }

        # Simulación: detectar declaraciones rezagadas
        # En implementación real, esto consultaría historial SAT
        cfdis = self._load_cfdis()

        meses_con_movimiento = set()
        for c in cfdis:
            fecha = c.get("fecha_emision", "")
            if fecha:
                meses_con_movimiento.add(fecha[:7])  # YYYY-MM

        # Si hay CFDIs desde 2022 y no declaraciones, sugerir regularización
        meses_list = sorted(list(meses_con_movimiento))
        if meses_list and meses_list[0] < "2024-01":
            result["declaraciones_pendientes"].append(
                {
                    "tipo": "regularización",
                    "periodo": f"{meses_list[0]} a {meses_list[-1]}",
                    "mensaje": "Detectado rezago de declaraciones. Se requiere regularización fiscal.",
                    "accion": "Presentar declaraciones complementarias o de actualización para los ejercicios faltantes.",
                }
            )

        # Recomendación: Suspensión de actividades
        meses_recientes = [m for m in meses_list if m >= "2026-01"]
        if not meses_recientes:
            result["riesgos_detectados"].append(
                {
                    "tipo": "inactividad",
                    "mensaje": "No se detectan movimientos en 2026.",
                    "accion": "Considerar suspensión temporal de actividades en el SAT para evitar multas por no presentar declaraciones.",
                }
            )

        return result

    def suggest_regularization(self) -> Dict:
        """
        Sugiere la mejor estrategia para regularizar rezago de declaraciones.
        """
        return {
            "status": "success",
            "estrategia": {
                "titulo": "Regularización de Declaraciones Rezagadas",
                "descripcion": "Para declaraciones no presentadas desde 2022, la mejor estrategia es:",
                "pasos": [
                    {
                        "paso": 1,
                        "titulo": "Reconstruir ingresos y egresos",
                        "descripcion": "Descargar todos los CFDIs del periodo desde el SAT.",
                        "accion": "Usar FiscoMind para sync completo desde 2022.",
                    },
                    {
                        "paso": 2,
                        "titulo": "Calcular ISR aproximado",
                        "descripcion": "Con base en ingresos - deducciones, estimar ISR por año.",
                        "accion": "Usar calculadora de FiscoMind con datos reales.",
                    },
                    {
                        "paso": 3,
                        "titulo": "Presentar declaraciones complementarias",
                        "descripcion": "Declarar años faltantes con datos reales.",
                        "accion": "Ir al portal SAT → Declaraciones → Complementarias",
                    },
                    {
                        "paso": 4,
                        "titulo": "Pago de actualizaciones y recargos",
                        "descripcion": "El SAT cobra actualización (inflación) + recargo (1.47% mensual).",
                        "accion": "Negociar convenio de pago si el monto es alto.",
                    },
                    {
                        "paso": 5,
                        "titulo": "Considerar programa de regularización",
                        "descripcion": "SAT ofrece programas de regularización con descuentos.",
                        "accion": "Consultar en portal SAT si hay programa vigente.",
                    },
                ],
                "recomendacion_final": "Si el ISR estimado por año es BAJO (< $5,000), conviene declarar todo junto. Si es ALTO (> $50,000), contratar contador para negociar convenio.",
                "riesgo_no_hacer_nada": "El SAT puede embargar cuentas, embargar bienes, o suspender actividades después de 2-3 años de no declarar.",
            },
        }

    def suggest_suspension(self) -> Dict:
        """
        Sugiere si conviene suspensión temporal o baja definitiva.
        """
        cfdis = self._load_cfdis()
        tiene_movimientos_2026 = any(
            c.get("fecha_emision", "").startswith("2026") for c in cfdis
        )

        if tiene_movimientos_2026:
            return {
                "status": "info",
                "mensaje": "Tienes movimientos en 2026. No es recomendable suspender actividades en este momento.",
                "alternativa": "Si no vas a facturar por 3+ meses, considera dar de baja el RFC como empresa y trabajar como empleado.",
            }

        return {
            "status": "success",
            "recomendacion": {
                "titulo": "Suspensión Temporal de Actividades",
                "beneficios": [
                    "No pagas ISR durante la suspensión",
                    "No presentas declaraciones (menos carga)",
                    "Mantienes RFC activo para reactivarte cuando quieras",
                    "Evitas multas por no declarar sin ingresos",
                ],
                "requisitos": [
                    "No tener facturas vigentes pendientes",
                    "No tener obligaciones fiscales pendientes",
                    "Aviso de suspensión en portal SAT",
                ],
                "como_hacerlo": [
                    "1. Portal SAT → Mi Portal → Actualización de Obligaciones",
                    "2. Seleccionar 'Suspensión de Actividades'",
                    "3. Indicar fecha de inicio de suspensión",
                    "4. Confirmar (se aplica en 24-48 hrs)",
                ],
                "recomendacion": "Si no tienes ingresos por 6+ meses, SUSPENSIÓN es la mejor opción. Si solo es temporal (1-2 meses) y tienes empleo en empresa moral, mantener activo está bien.",
            },
        }

    def optimize_legal(self) -> Dict:
        """
        Sugiere estrategias legales de optimización fiscal 2026.
        """
        cfdis = self._load_cfdis()

        total_ingresos = sum(
            float(c.get("monto", 0)) for c in cfdis if c.get("efecto") == "I"
        )
        total_egresos = sum(
            float(c.get("monto", 0)) for c in cfdis if c.get("efecto") == "E"
        )

        # Verificar si está cerca de cambio de tarifa
        ingreso_anual_est = total_ingresos * 4  # Proyección anual
        tarifa_actual = self.TARIFAS_ISR[0]
        for t in self.TARIFAS_ISR:
            if ingreso_anual_est > t["limite"]:
                tarifa_actual = t

        sugerencias = []

        # 1. Si está cerca de cambio de tarifa
        prox_tarifa_idx = self.TARIFAS_ISR.index(tarifa_actual) + 1
        if prox_tarifa_idx < len(self.TARIFAS_ISR):
            prox_tarifa = self.TARIFAS_ISR[prox_tarifa_idx]
            if (
                ingreso_anual_est > prox_tarifa["limite"] * 0.9
            ):  # 90% del siguiente nivel
                sugerencias.append(
                    {
                        "tipo": "estrategia_critica",
                        "titulo": "⚠️ Alerta: Posible cambio de tarifa ISR",
                        "mensaje": f"Con ${ingreso_anual_est:,.2f} anuales, estás cerca del siguiente nivel de tarifa ({prox_tarifa['tasa'] * 100:.1f}%). Considera aumentar deducciones antes de fin de año para evitar pagar más ISR.",
                        "acciones": [
                            "Aumentar deducciones: colegiaturas ($16,980/alumno), médicos (hasta 15% de ingresos), donativos (7% de utilidad fiscal)",
                            "Pagar antes de diciembre: software, capacitación, equipo de cómputo",
                            "Considerar inversión en activos deducibles (depreciación acelerada)",
                        ],
                    }
                )

        # 2. Alerta de efectivo
        pagos_efectivo = [
            c
            for c in cfdis
            if float(c.get("monto", 0)) > 2000 and c.get("forma_pago") == "01"
        ]
        if pagos_efectivo:
            sugerencias.append(
                {
                    "tipo": "advertencia",
                    "titulo": "🚨 Pagos en efectivo > $2,000",
                    "mensaje": f"Tienes {len(pagos_efectivo)} CFDIs con pagos en efectivo > $2,000. Estos gastos NO son deducibles según normativa 2026.",
                    "acciones": [
                        "Futuro: Paga todo con transferencia, tarjeta o cheque",
                        "Actual: Si ya facturaste, no puedes deducirlos. Considera si puedes re-facturar mediante el emisor.",
                    ],
                }
            )

        # 3. Deducción de colegiaturas (nueva 2026)
        colegiaturas = [
            c for c in cfdis if "colegiatura" in c.get("nombre_emisor", "").lower()
        ]
        if colegiaturas:
            total_coleg = sum(float(c.get("monto", 0)) for c in colegiaturas)
            if total_coleg > 16980:
                sugerencias.append(
                    {
                        "tipo": "estrategia",
                        "titulo": "🎓 Deducción de colegiaturas",
                        "mensaje": f"Tienes ${total_coleg:,.2f} en colegiaturas. El tope es $16,980 por alumno. Divide la deducción entre cónyuges para maximizar.",
                        "acciones": [
                            "Un cónyuge deduce $16,980, el otro deduce el resto",
                            "Asegúrate de que la factura esté a nombre del que declara",
                            "Guarda el certificado de colegiatura del alumno",
                        ],
                    }
                )

        # 4. Donativos (nueva tasa 7%)
        donativos = [
            c
            for c in cfdis
            if any(
                x in c.get("nombre_emisor", "").lower()
                for x in ["donativo", "fundacion", "donacion"]
            )
        ]
        if not donativos:
            utilidad_fiscal = max(0, total_ingresos - total_egresos)
            tope_donativos = utilidad_fiscal * 0.07
            if tope_donativos > 5000:
                sugerencias.append(
                    {
                        "tipo": "estrategia",
                        "titulo": "💰 Donativos deducibles",
                        "mensaje": f"Podrías deducir hasta ${tope_donativos:,.2f} en donativos (7% de tu utilidad fiscal). Busca instituciones con calidad de donee (hospitales públicos, fundaciones).",
                        "acciones": [
                            "Verificar calidad de donee en: https://www.sat.gob.mx/tu-sitio/donatarias",
                            "Solicitar factura a nombre de quien declara",
                            "Guardar constancia de donativo",
                        ],
                    }
                )

        return {
            "status": "success",
            "proyeccion_anual_estimada": ingreso_anual_est,
            "tarifa_isr_aplicada": f"{tarifa_actual['tasa'] * 100:.1f}%",
            "isr_estimado_anual": (ingreso_anual_est - tarifa_actual["cuota_fija"])
            * tarifa_actual["tasa"],
            "sugerencias": sugerencias,
            "fecha_actualizacion": "2026-05-13",
        }
