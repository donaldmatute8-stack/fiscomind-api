"""
FiscoMind - Motor de Inteligencia Fiscal
Piensa como contador: analiza situación, detecta riesgos, propone estrategias.
Integra datos de CFDIs, estados de cuenta, historial SAT, y calcula caminos óptimos.
"""

import json
from typing import Dict, List
from datetime import date, datetime
from collections import defaultdict


class FiscalIntelligenceEngine:
    """
    Motor de inteligencia fiscal de FiscoMind.

    Entrada:
    - CFDIs (recibidos + emitidos)
    - Estados de cuenta (movimientos bancarios)
    - Historial de declaraciones
    - Situación del contribuyente (régimen, actividad)

    Salida:
    - Análisis completo de riesgo
    - Escenarios fiscales
    - Estrategia recomendada
    - Acciones prioritarias
    """

    def __init__(self, rfc: str = "MUTM8610091NA", regimen: str = "PFAE-general"):
        self.rfc = rfc
        self.regimen = regimen
        self.context = {}

    def analyze(
        self,
        cfdis: List[Dict],
        movimientos: List[Dict],
        facturas_emitidas: List[Dict],
        historial_declaraciones: Dict = None,
    ) -> Dict:
        """
        Análisis completo que un contador haría al revisar un caso.
        """

        # 1. DETECTAR INCONSISTENCIAS
        inconsistencias = self._detectar_inconsistencias(
            cfdis, movimientos, facturas_emitidas
        )

        # 2. CALCULAR INGRESOS REALES
        ingresos = self._calcular_ingresos_reales(cfdis, movimientos, facturas_emitidas)

        # 3. CALCULAR OBLIGACIONES
        obligaciones = self._calcular_obligaciones(ingresos)

        # 4. DETECTAR RIESGOS SAT
        riesgos = self._evaluar_riesgo_sat(ingresos, inconsistencias)

        # 5. GENERAR ESCENARIOS
        escenarios = self._generar_escenarios(ingresos, obligaciones)

        # 6. ESTRATEGIA FINAL
        estrategia = self._recomendar_estrategia(riesgos, escenarios, self.context)

        return {
            "status": "success",
            "rfc": self.rfc,
            "fecha_analisis": datetime.now().isoformat(),
            "resumen_ejecutivo": self._generar_resumen_ejecutivo(
                ingresos, obligaciones, riesgos
            ),
            "ingresos_detectados": ingresos,
            "obligaciones_fiscales": obligaciones,
            "inconsistencias_detectadas": inconsistencias,
            "riesgo_sat": riesgos,
            "escenarios": escenarios,
            "estrategia_recomendada": estrategia,
            "acciones_inmediatas": estrategia["acciones"],
            "proximo_paso": estrategia["proximo_paso"],
        }

    def _detectar_inconsistencias(self, cfdis, movimientos, emitidos) -> List[Dict]:
        """Detecta lo que un contador vería a primera vista."""
        inconsistencias = []

        # Inconsistencia 1: Facturas emitidas sin ingreso bancario correspondiente
        total_emitido = sum(
            e.get("monto", 0) for e in emitidos if e.get("estatus") == "1"
        )
        total_depositos_terceros = sum(
            m.get("monto", 0)
            for m in movimientos
            if m.get("tipo") == "deposito" and m.get("categoria") == "deposito_tercero"
        )

        if total_emitido > 0 and total_depositos_terceros == 0:
            inconsistencias.append(
                {
                    "tipo": "CRITICA",
                    "codigo": "emitido_sin_cobro",
                    "descripcion": f"Emitiste ${total_emitido:,.2f} en facturas pero no hay depósitos de terceros en estados de cuenta",
                    "explicacion": "El SAT compara ingresos bancarios vs. facturas emitidas. Si facturaste pero no cobraste, sigue siendo ingreso. Si cobraste sin facturar, es ingreso omitido.",
                    "recomendacion": "Verificar si el cobro fue en efectivo, a otra cuenta, o el cliente aún no paga.",
                    "riesgo": "MEDIO",
                }
            )

        # Inconsistencia 2: Depósitos recurrentes sin factura
        terceros_recurrentes = defaultdict(float)
        for m in movimientos:
            if m.get("categoria") == "deposito_tercero":
                origen = m.get("concepto", "")
                terceros_recurrentes[origen] += m.get("monto", 0)

        for origen, total in terceros_recurrentes.items():
            if total > 20000:  # Más de $20,000 del mismo origen
                inconsistency = {
                    "tipo": "ALTA",
                    "codigo": "deposito_recurrente_sin_factura",
                    "descripcion": f"${total:,.2f} de '{origen}' sin factura asociada",
                    "explicacion": "Depósitos recurrentes del mismo origen pueden ser ingresos recurrentes. El SAT puede interpretarlos como actividad económica.",
                    "recomendacion": "Si es ingreso de negocio: facturar. Si es préstamo: contrato. Si es regalo: carta de regalo.",
                    "riesgo": "ALTO",
                }
                inconsistencias.append(inconsistency)

        # Inconsistencia 3: Duplicados en facturas emitidas
        uuids = [e.get("uuid", "") for e in emitidos]
        if len(uuids) != len(set(uuids)):
            inconsistencias.append(
                {
                    "tipo": "CRITICA",
                    "codigo": "facturas_duplicadas",
                    "descripcion": "Hay facturas duplicadas en emitidos",
                    "explicacion": "Puede ser error de registro o facturas reales duplicadas que deben cancelarse.",
                    "recomendacion": "Verificar en SAT portal cuáles están vigentes y cancelar las sobrantes.",
                    "riesgo": "ALTO",
                }
            )

        return inconsistencias

    def _calcular_ingresos_reales(self, cfdis, movimientos, emitidos) -> Dict:
        """Distingue lo que es ingreso real vs. transferencias propias."""

        # Ingresos por facturas emitidas vigentes
        ingresos_facturados = sum(
            e.get("monto", 0) for e in emitidos if e.get("estatus") == "1"
        )

        # Base gravable (subtotal sin IVA)
        # Asumimos promedio 16% IVA
        base_gravable_estimada = (
            ingresos_facturados / 1.16 if ingresos_facturados > 0 else 0
        )

        # Depósitos de terceros
        depositos_terceros = sum(
            m.get("monto", 0)
            for m in movimientos
            if m.get("categoria") == "deposito_tercero"
        )

        # Transferencias propias (NO son ingresos)
        transferencias_propias = sum(
            m.get("monto", 0)
            for m in movimientos
            if m.get("categoria") == "transferencia_propia"
        )

        return {
            "facturado_vigente": round(ingresos_facturados, 2),
            "base_gravable_estimada": round(base_gravable_estimada, 2),
            "depositos_terceros_sin_clasificar": round(depositos_terceros, 2),
            "transferencias_propias": round(transferencias_propias, 2),
            "total_potencialmente_declarable": round(
                ingresos_facturados + depositos_terceros, 2
            ),
        }

    def _calcular_obligaciones(self, ingresos) -> Dict:
        """Calcula ISR e IVA estimados."""
        base = ingresos.get("base_gravable_estimada", 0)

        return {
            "iva_trasladado": round(base * 0.16, 2),
            "isr_estimado": round(base * 0.30, 2),
            "reserva_mensual": round(
                base * 0.30 / 12, 2
            ),  # Si facturó una vez, dividir
            "total_estimado": round(base * 0.46, 2),
        }

    def _evaluar_riesgo_sat(self, ingresos, inconsistencias) -> Dict:
        """Evalúa probabilidad de que el SAT detecte problemas."""

        nivel = "BAJO"
        factores = []

        if ingresos.get("depositos_terceros_sin_clasificar", 0) > 50000:
            nivel = "ALTO"
            factores.append("$50,000+ en depósitos de terceros sin facturar")
        elif ingresos.get("depositos_terceros_sin_clasificar", 0) > 10000:
            nivel = "MEDIO"
            factores.append("$10,000+ en depósitos sin clasificar")

        criticas = [i for i in inconsistencias if i["tipo"] == "CRITICA"]
        if len(criticas) >= 2:
            nivel = "ALTO"
            factores.append("2+ inconsistencias críticas")

        return {
            "nivel": nivel,
            "probabilidad_auditoria": "BAJA"
            if nivel == "BAJO"
            else ("MEDIA" if nivel == "MEDIO" else "ALTA"),
            "factores_riesgo": factores,
            "periodo_critico": "Marzo-Abril 2026: depositos recurrentes + facturas recientes",
        }

    def _generar_escenarios(self, ingresos, obligaciones) -> List[Dict]:
        """Genera caminos posibles como un contador."""

        base = ingresos.get("base_gravable_estimada", 0)

        return [
            {
                "nombre": "ESCENARIO A: Regularizar y pagar",
                "descripcion": "Presentar declaraciones correctas, pagar impuestos calculados.",
                "costo": obligaciones["total_estimado"],
                "ventaja": "Quedas regularizado. Bajo riesgo SAT.",
                "desventaja": "Pago inmediato alto si no hay reserva.",
                "recomendado": True,
            },
            {
                "nombre": "ESCENARIO B: Facilidades de pago",
                "descripcion": "Declarar correcto pero pagar a 6-12 meses.",
                "costo": obligaciones["total_estimado"],
                "costo_con_recargos": round(obligaciones["total_estimado"] * 1.09, 2),
                "ventaja": "Menos presión de liquidez",
                "desventaja": "Recargos adicionales",
                "recomendado": True,
            },
            {
                "nombre": "ESCENARIO C: Declarar en ceros (ilegal)",
                "descripcion": "NO declarar ingresos facturados. Defraudación fiscal.",
                "costo": 0,
                "riesgo": "Multa 20-100% + posible cárcel. El SAT ya te invitó.",
                "ventaja": "Ninguna a largo plazo",
                "desventaja": "Criminal. NO hacer.",
                "recomendado": False,
            },
        ]

    def _recomendar_estrategia(self, riesgo, escenarios, context) -> Dict:
        """Recomienda como contador senior."""

        nivel_riesgo = riesgo.get("nivel", "MEDIO")

        if nivel_riesgo == "ALTO":
            estrategia = {
                "nombre": "PRIORIDAD 1: Regularizar inmediatamente",
                "rationale": "Riesgo ALTO detectado. El SAT ya te invitó. La prescripción es débil con inconsistencias reales.",
                "acciones": [
                    "Paso 1: Presentar todas las declaraciones pendientes (marzo, abril, mayo)",
                    "Paso 2: Calcular impuestos reales con base en facturas",
                    "Paso 3: Si no puedes pagar: solicitar facilidades de pago SAT",
                    "Paso 4: Documentar depósitos de terceros (préstamos, reembolsos)",
                    "Paso 5: Si no vas a facturar más: suspensión temporal de actividades",
                    "Paso 6: Guardar todos los acuses",
                ],
                "proximo_paso": "Presentar abril HOY (vence 17 mayo). Luego presentar marzo con datos correctos.",
            }
        elif nivel_riesgo == "MEDIO":
            estrategia = {
                "nombre": "PRIORIDAD 2: Presentar mensual y ordenar pasado",
                "rationale": "Riesgo MEDIO. No hay alertas críticas pero hay inconsistencias.",
                "acciones": [
                    "Paso 1: Presentar período actual (mayo o abril si no lo hiciste)",
                    "Paso 2: Regularizar rezago histórico (2022-2025)",
                    "Paso 3: Documentar ingresos no facturados o facturarlos",
                    "Paso 4: Evaluar suspensión si no hay actividad futura",
                ],
                "proximo_paso": "Presentar al mes actual, luego regularizar pasado.",
            }
        else:
            estrategia = {
                "nombre": "PRIORIDAD 3: Mantener actualizado",
                "rationale": "Riesgo BAJO. Caso sencillo, solo mantener al día.",
                "acciones": [
                    "Seguir declarando mensualmente",
                    "Juntar CFDIs de gastos deducibles",
                    "Evaluar suspensión si baja actividad",
                ],
                "proximo_paso": "Continuar con declaraciones normales.",
            }

        return estrategia

    def _generar_resumen_ejecutivo(self, ingresos, obligaciones, riesgo) -> str:
        base = ingresos.get("base_gravable_estimada", 0)
        iva = obligaciones.get("iva_trasladado", 0)
        isr = obligaciones.get("isr_estimado", 0)
        total = iva + isr

        return (
            f"Base gravable detectada: ${base:,.2f}. "
            f"ISR estimado: ${isr:,.2f}. IVA: ${iva:,.2f}. "
            f"Total a pagar: ${total:,.2f}. "
            f"Riesgo SAT: {riesgo['nivel']}. "
            f"{riesgo['probabilidad_auditoria']} probabilidad de auditoría."
        )


def analizar_situacion_fiscal(data: Dict) -> Dict:
    """Entry point rápido del motor de inteligencia."""
    engine = FiscalIntelligenceEngine(
        rfc=data.get("rfc", "MUTM8610091NA"),
        regimen=data.get("regimen", "PFAE-general"),
    )
    engine.context = data.get("contexto", {})

    return engine.analyze(
        cfdis=data.get("cfdis", []),
        movimientos=data.get("movimientos", []),
        facturas_emitidas=data.get("emitidos", []),
        historial_declaraciones=data.get("historial", {}),
    )
