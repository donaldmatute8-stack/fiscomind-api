"""
FiscoMind - Motor de Optimización Fiscal (Diferenciador vs Konta)
Analiza CFDIs del usuario y genera estrategias para reducir ISR legalmente.
"""

import os
import json
from datetime import datetime, date
from typing import Dict, List, Optional
from pathlib import Path


class OptimizationEngine:
    """
    Motor de inteligencia fiscal que analiza patrones de gasto
    y sugiere estrategias legales para optimizar la carga tributaria.
    """

    # Catálogo de categorías deducibles (basado en LISR)
    CATEGORIAS_DEDUCIBLES = {
        "renta_oficina": {"max_pct": 1.0, "descripcion": "Renta de oficina o local"},
        "servicios_profesionales": {
            "max_pct": 1.0,
            "descripcion": "Servicios profesionales",
        },
        "software": {"max_pct": 0.9, "descripcion": "Software y tecnología"},
        "capacitacion": {"max_pct": 1.0, "descripcion": "Capacitación"},
        "viaticos": {"max_pct": 0.85, "descripcion": "Viáticos (con evidencia)"},
        "combustible": {
            "max_pct": 0.8,
            "descripcion": "Combustible (con control vehicular)",
        },
        "mantenimiento": {
            "max_pct": 0.9,
            "descripcion": "Mantenimiento y reparaciones",
        },
        "publicidad": {"max_pct": 1.0, "descripcion": "Publicidad y marketing"},
        "telefonia_internet": {"max_pct": 0.85, "descripcion": "Teléfono e internet"},
        "servicios_basicos": {"max_pct": 0.85, "descripcion": "Luz, agua, gas"},
        "seguros": {"max_pct": 0.9, "descripcion": "Seguros de activos"},
        "donativos": {
            "max_pct": 0.07,
            "descripcion": "Donativos (7% de utilidad fiscal)",
        },
        "muebles_equipo": {
            "max_pct": 1.0,
            "descripcion": "Muebles y equipo de oficina",
        },
        "intereses_prestamos": {
            "max_pct": 1.0,
            "descripcion": "Intereses de préstamos (deductibles)",
        },
    }

    def __init__(self, data_dir: str = "/app/data/users/marco_test"):
        self.data_dir = Path(data_dir)
        self.cache_file = self.data_dir / "optimization_cache.json"

    def _load_cfdis(self) -> List[Dict]:
        """Carga CFDIs recibidos del SAT"""
        cfdis = []
        sync_files = sorted(self.data_dir.glob("sat_sync_*.json"), reverse=True)
        for sf in sync_files:
            try:
                with open(sf) as f:
                    data = json.load(f)
                for cfdi in data.get("cfdis", []):
                    if cfdi.get("efecto") == "E" and cfdi.get("estatus") == "1":
                        cfdis.append(cfdi)
            except:
                continue
        return cfdis

    def _categorizar_gasto(self, descripcion: str, emisor: str) -> str:
        """Clasifica un gasto en categoría deducible"""
        desc_lower = descripcion.lower()
        emisor_lower = emisor.lower()

        if any(x in desc_lower for x in ["renta", "arrendamiento", "local"]):
            return "renta_oficina"
        elif any(
            x in desc_lower for x in ["asesor", "consultor", "abogado", "contador"]
        ):
            return "servicios_profesionales"
        elif any(x in desc_lower for x in ["software", "licencia", "saas", "cloud"]):
            return "software"
        elif any(
            x in desc_lower for x in ["curso", "capacitacion", "diplomado", "taller"]
        ):
            return "capacitacion"
        elif any(x in desc_lower for x in ["hotel", "vuelo", "viaje", "uber", "taxi"]):
            return "viaticos"
        elif any(
            x in desc_lower for x in ["gasolina", "combustible", "gasolinera", "pemex"]
        ):
            return "combustible"
        elif any(x in desc_lower for x in ["mantenimiento", "reparacion", "servicio"]):
            return "mantenimiento"
        elif any(
            x in desc_lower
            for x in ["publicidad", "marketing", "ads", "google", "facebook", "meta"]
        ):
            return "publicidad"
        elif any(
            x in desc_lower
            for x in ["telefono", "celular", "internet", "wifi", "telcel", "att"]
        ):
            return "telefonia_internet"
        elif any(x in desc_lower for x in ["luz", "agua", "cfe"]):
            return "servicios_basicos"
        elif any(x in desc_lower for x in ["seguro", "axa", "gnp", "qualitas"]):
            return "seguros"
        elif any(x in desc_lower for x in ["donativo", "donacion", "fundacion"]):
            return "donativos"
        elif any(x in desc_lower for x in ["mueble", "escritorio", "silla", "equipo"]):
            return "muebles_equipo"
        elif any(x in desc_lower for x in ["interes", "financiamiento", "credito"]):
            return "intereses_prestamos"
        else:
            return "otros"

    def generate_report(self) -> Dict:
        """
        Genera reporte completo de optimización fiscal con recomendaciones.
        """
        cfdis = self._load_cfdis()

        # Totales
        total_gastos = sum(float(c.get("monto", 0)) for c in cfdis)

        # Por categoría
        gastos_por_categoria = {}
        for cfdi in cfdis:
            monto = float(cfdi.get("monto", 0))
            cat = self._categorizar_gasto(
                cfdi.get("nombre_emisor", ""), cfdi.get("nombre_emisor", "")
            )
            if cat not in gastos_por_categoria:
                gastos_por_categoria[cat] = {"monto": 0, "count": 0}
            gastos_por_categoria[cat]["monto"] += monto
            gastos_por_categoria[cat]["count"] += 1

        # Sugerencias de optimización
        sugerencias = self._generar_sugerencias(gastos_por_categoria, total_gastos)

        # Riesgos detectados
        riesgos = self._detectar_riesgos(gastos_por_categoria, total_gastos)

        return {
            "status": "success",
            "total_gastos": total_gastos,
            "cantidad_cfdis": len(cfdis),
            "gastos_por_categoria": gastos_por_categoria,
            "sugerencias": sugerencias,
            "riesgos": riesgos,
            "fecha_analisis": datetime.now().isoformat(),
        }

    def _generar_sugerencias(self, gastos: Dict, total: float) -> List[Dict]:
        """Genera recomendaciones personalizadas"""
        sugerencias = []

        # 1. Huecos de deducción
        for cat_key, cat_info in self.CATEGORIAS_DEDUCIBLES.items():
            if cat_key not in gastos and cat_key not in [
                "donativos",
                "intereses_prestamos",
            ]:
                sugerencias.append(
                    {
                        "tipo": "oportunidad",
                        "categoria": cat_key,
                        "titulo": f"💡 {cat_info['descripcion']}",
                        "mensaje": f"No tienes gastos en '{cat_info['descripcion']}'. Considera que esta categoría es deducible al {cat_info['max_pct'] * 100:.0f}%.",
                        "potencial_ahorro_estimado": total * 0.05 * cat_info["max_pct"],
                        "accion": f"Genera CFDIs de {cat_info['descripcion']} que uses para tu actividad.",
                    }
                )

        # 2. Donativos (7% de utilidad)
        donativos = gastos.get("donativos", {}).get("monto", 0)
        utilidad_fiscal_estimada = total * 0.3  # asumiendo 30% de margen
        tope_donativos = utilidad_fiscal_estimada * 0.07
        if donativos < tope_donativos * 0.5:
            sugerencias.append(
                {
                    "tipo": "estrategia",
                    "categoria": "donativos",
                    "titulo": "📈 Maximiza donativos",
                    "mensaje": f"Solo tienes ${donativos:,.2f} en donativos. Podrías deducir hasta ${tope_donativos:,.2f} (7% de utilidad fiscal).",
                    "potencial_ahorro_estimado": (tope_donativos - donativos) * 0.30,
                    "accion": "Considera donativos a instituciones autorizadas (Donee).",
                }
            )

        # 3. Publicidad y marketing
        pub = gastos.get("publicidad", {}).get("monto", 0)
        if total > 0 and (pub / total) < 0.05:
            sugerencias.append(
                {
                    "tipo": "estrategia",
                    "categoria": "publicidad",
                    "titulo": "📢 Publicidad deducible",
                    "mensaje": "Tus gastos en publicidad son bajos en relación a tus ingresos. El 100% es deducible.",
                    "potencial_ahorro_estimado": total * 0.02,
                    "accion": "Factura publicidad digital, impresos, eventos. Todo es deducible al 100%.",
                }
            )

        # 4. Capacitación
        cap = gastos.get("capacitacion", {}).get("monto", 0)
        if total > 0 and cap == 0:
            sugerencias.append(
                {
                    "tipo": "estrategia",
                    "categoria": "capacitacion",
                    "titulo": "🎓 Capacitación fiscal",
                    "mensaje": "No tienes gastos en capacitación registrados. Cursos, diplomados y talleres relacionados con tu giro son deducibles al 100%.",
                    "potencial_ahorro_estimado": total * 0.03,
                    "accion": "Inscribe a tu equipo o a ti en cursos relacionados con tu actividad.",
                }
            )

        return sorted(
            sugerencias, key=lambda x: x["potencial_ahorro_estimado"], reverse=True
        )

    def _detectar_riesgos(self, gastos: Dict, total: float) -> List[Dict]:
        """Detecta posibles riesgos fiscales"""
        riesgos = []

        # 1. Gastos deducibles sin CFDI
        # Esto requiere validación manual, pero alertamos
        riesgos.append(
            {
                "tipo": "advertencia",
                "titulo": "⚠️ No olvides facturar todo",
                "mensaje": "Recuerda que solo puedes deducir gastos que estén fiscalmente comprobados (CFDI).",
                "severidad": "media",
            }
        )

        # 2. Viáticos altos sin evidencia
        via = gastos.get("viaticos", {}).get("monto", 0)
        if via > total * 0.15:
            riesgos.append(
                {
                    "tipo": "riesgo",
                    "titulo": "🚨 Viáticos elevados",
                    "mensaje": f"Tus viáticos (${via:,.2f}) representan >15% de tus gastos. El SAT puede pedir evidencia (agenda, constancia, etc.).",
                    "severidad": "alta",
                }
            )

        # 3. Combustible sin control vehicular
        comb = gastos.get("combustible", {}).get("monto", 0)
        if comb > total * 0.10:
            riesgos.append(
                {
                    "tipo": "riesgo",
                    "titulo": "⛽ Combustible sin control",
                    "mensaje": "El combustible requiere control vehicular (bitácora, placas, uso exclusivo). Si no lo tienes, corrige antes de declarar.",
                    "severidad": "alta",
                }
            )

        return riesgos

    def project_isr(self) -> Dict:
        """
        Proyecta el ISR del año en base al trimestre actual.
        """
        cfdis = self._load_cfdis()

        total_ingresos = sum(
            float(c.get("monto", 0)) for c in cfdis if c.get("efecto") == "I"
        )
        total_egresos = sum(
            float(c.get("monto", 0)) for c in cfdis if c.get("efecto") == "E"
        )

        # Deducción simplificada (30%)
        deduccion = total_egresos * 0.30
        base_gravable = max(0, total_ingresos - deduccion)

        # ISR trimestral
        isr_trimestral = base_gravable * 0.30
        isr_anual = isr_trimestral * 4

        # Detectar salto de tarifa
        # Tarifas estimadas para Personas Físicas (2026)
        tarifas = [
            {"limite": 89544.00, "tasa": 0.0194, "base": 0},
            {"limite": 127060.00, "tasa": 0.0640, "base": 1714},
            {"limite": 296380.00, "tasa": 0.1088, "base": 12629},
            {"limite": 564170.00, "tasa": 0.1600, "base": 45264},
            {"limite": 752240.00, "tasa": 0.1792, "base": 107144},
            {"limite": 2256720.00, "tasa": 0.2136, "base": 140936},
            {"limite": float("inf"), "tasa": 0.3000, "base": 460737},
        ]

        ingreso_anual_est = total_ingresos * 4
        tarifa_actual = tarifas[0]
        for t in tarifas:
            if ingreso_anual_est > t["limite"]:
                tarifa_actual = t

        isr_real_estimado = (ingreso_anual_est - tarifa_actual["base"]) * tarifa_actual[
            "tasa"
        ]

        return {
            "trimestre_actual": {
                "ingresos": total_ingresos,
                "egresos": total_egresos,
                "deduccion_estimada": deduccion,
                "base_gravable": base_gravable,
                "isr_estimado": isr_trimestral,
            },
            "proyeccion_anual": {
                "ingresos_estimados": ingreso_anual_est,
                "egresos_estimados": total_egresos * 4,
                "isr_anual_estimado": isr_anual,
                "isr_real_estimado": isr_real_estimado,
                "tarifa_aplicada": tarifa_actual["tasa"],
                "diferencia": isr_real_estimado - isr_anual,
            },
        }
