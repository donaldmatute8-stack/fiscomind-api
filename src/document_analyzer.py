"""
FiscoMind - Motor de Análisis de Documentos Fiscales
Recibe texto/CSV de estados de cuenta y analiza movimientos automáticamente.
"""

import re
import json
from typing import Dict, List, Tuple
from datetime import datetime
from collections import defaultdict


class EstadoCuentaAnalyzer:
    """Analiza estados de cuenta y clasifica movimientos fiscalmente."""

    # Palabras clave para clasificar movimientos
    TRANSFERENCIAS_PROPIAS = [
        "fondeadora",
        "nu debito",
        "nu mexico",
        "banregio",
        "scotiabank",
        "santander",
        "bbva",
        "bancoppel",
        "hsbc",
        "inbursa",
        "banorte",
        "transferencia a marco",
        "transferencia desde marco",
        "marco nu debito",
        "marco banregio",
        "fondeo",
        "retiro cajero",
    ]

    GASTOS_DEDUCIBLES = [
        "namecheap",
        "thirdweb",
        "ollama",
        "runpod",
        "openai",
        "github",
        "gitlab",
        "aws",
        "azure",
        "google cloud",
        "digitalocean",
        "linode",
        "vercel",
        "netlify",
        "heroku",
        "stripe",
        "twilio",
        "sendgrid",
        "gasol",
        "gasolinera",
        "pemex",
        "shell",
        "mobil",
        "gpo octano",
        "oficina",
        "cowork",
        "renta",
        "arrendamiento",
        "contador",
        "abogado",
        "diseñador",
        "desarrollador",
        "programador",
        "internet",
        "telcel",
        "att",
        "totalplay",
        "izzi",
        "infinitum",
        "uber",
        "didi",
        "cabify",
        "transporte",
        "avion",
        "vuelo",
        "hotel",
        "hospedaje",
        "airbnb",
    ]

    GASTOS_PERSONALES = [
        "pizza",
        "restaurant",
        "rest bar",
        "cafe",
        "cafeteria",
        "disney",
        "netflix",
        "spotify",
        "youtube",
        "prime",
        "gimnasio",
        "fitness",
        "crossfit",
        "golf",
        "cine",
        "temu",
        "shein",
        "amazon",
        "mercadolibre",
        "liverpool",
        "costco",
        "walmart",
        "soriana",
        "chedraui",
        "oxxo",
        "7-eleven",
        "familiar",
        "esposa",
        "hija",
        "hijo",
        "mama",
        "papa",
        "mercadopago *coficent",
        "mercadopago *crfitnes",
    ]

    FAMILIARES = [
        "susana del toro",
        "juan muñoz",
        "ivette cortes",
        "cesar muñoz",
        "doña mary",
        "mary hija",
        "illy alonso",
        "diego valerio",
        "manuel gllavalos",
        "israel mecanico",
        "alejandro patron",
        "jesus bautista",
        "angel jahir",
        "raul ernesto",
        "paulina juarez",
        "luis eduardo",
        "genaro daniel",
        "celina del toro",
        "oswaldo guadalupe",
    ]

    def __init__(self):
        self.movimientos = []
        self.resumen = {}

    def parse_tabla(self, texto: str) -> List[Dict]:
        """
        Parsea tabla de movimientos bancarios desde texto plano.
        Soporta formatos comunes: CSV tabulado, columnas separados por espacios, pipes.
        """
        movimientos = []
        lineas = [l.strip() for l in texto.split("\n") if l.strip()]

        for linea in lineas:
            # Intentar detectar fecha DD/MM/YYYY o DD-MM-YYYY
            match_fecha = re.search(r"(\d{2}[/-]\d{2}[/-]\d{4})", linea)
            if not match_fecha:
                continue

            fecha = match_fecha.group(1)

            # Buscar monto: patrón $X,XXX.XX o $XXXX.XX o simplemente números
            match_monto = re.findall(r"[\$\s]?([\d,]+\.\d{2})", linea)
            if not match_monto:
                continue

            # Tomar el monto más largo/número más grande como el principal
            monto_str = max(match_monto, key=lambda x: float(x.replace(",", "")))
            monto = float(monto_str.replace(",", ""))

            # Detectar tipo: Depósito o Retiro
            tipo = "desconocido"
            if "depósito" in linea.lower() or "deposito" in linea.lower():
                tipo = "deposito"
            elif "retiro" in linea.lower():
                tipo = "retiro"
            elif "transferencia a" in linea.lower():
                tipo = "retiro"
            elif (
                "transferencia desde" in linea.lower()
                or "transferencia de" in linea.lower()
            ):
                tipo = "deposito"
            elif linea.startswith(fecha):
                # Verificar signo del monto
                # Si hay "$-" o monto negativo
                if "-$" in linea or "-$" in linea.replace(" ", ""):
                    tipo = "retiro"
                else:
                    tipo = "deposito"

            # Extraer concepto (todo lo que queda entre fecha y monto)
            concepto = (
                linea.replace(fecha, "")
                .replace(f"${monto_str}", "")
                .replace(f"-{monto_str}", "")
                .strip()
            )
            concepto = re.sub(r"[\$\-,\d\.]+", "", concepto).strip()
            concepto = re.sub(r"\s+", " ", concepto).strip()

            movimientos.append(
                {
                    "fecha_raw": fecha,
                    "fecha_iso": self._parse_fecha(fecha),
                    "concepto": concepto,
                    "monto": monto,
                    "tipo": tipo,
                    "linea_original": linea,
                }
            )

        return movimientos

    def _parse_fecha(self, fecha_str: str) -> str:
        """Normaliza fecha a ISO."""
        try:
            for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"]:
                try:
                    return datetime.strptime(fecha_str, fmt).strftime("%Y-%m-%d")
                except:
                    continue
        except:
            pass
        return fecha_str

    def clasificar_movimiento(self, mov: Dict) -> Dict:
        """
        Clasifica un movimiento en categorías fiscales.
        """
        concepto_lower = mov.get("concepto", "").lower()
        monto = mov.get("monto", 0)
        tipo = mov.get("tipo", "desconocido")

        # Detectar transferencias propias
        if any(p in concepto_lower for p in self.TRANSFERENCIAS_PROPIAS):
            return {
                "categoria": "transferencia_propia",
                "subcategoria": "entre_cuentas",
                "deducible": False,
                "ingreso_gravable": False,
                "riesgo_sat": "ninguno",
                "nota": "Movimiento entre cuentas del mismo titular",
            }

        # Detectar depósitos de familiares
        if any(f in concepto_lower for f in self.FAMILIARES):
            return {
                "categoria": "ingreso_familiar",
                "subcategoria": "tercero_familiar",
                "deducible": False,
                "ingreso_gravable": False,
                "riesgo_sat": "medio",
                "nota": "Depósito de familiar. NO es ingreso de negocio, pero el SAT puede cuestionarlo sin documentación.",
            }

        # Detectar gastos personales
        if any(p in concepto_lower for p in self.GASTOS_PERSONALES):
            return {
                "categoria": "gasto_personal",
                "subcategoria": "no_deducible",
                "deducible": False,
                "ingreso_gravable": False,
                "riesgo_sat": "ninguno",
                "nota": "Gasto personal. NO es deducible fiscalmente.",
            }

        # Detectar gastos deducibles
        for ded in self.GASTOS_DEDUCIBLES:
            if ded in concepto_lower:
                return {
                    "categoria": "gasto_deducible",
                    "subcategoria": ded,
                    "deducible": False,  # Inicialmente FALSE - necesita CFDI
                    "ingreso_gravable": False,
                    "riesgo_sat": "ninguno",
                    "nota": f"Potencialmente deducible si tiene CFDI de {ded.upper()}. SIN CFDI no reduce impuestos.",
                }

        # Depósitos de terceros no clasificados (POSIBLE INGRESO)
        if tipo == "deposito":
            return {
                "categoria": "deposito_tercero",
                "subcategoria": "sin_clasificar",
                "deducible": False,
                "ingreso_gravable": "desconocido",
                "riesgo_sat": "alto",
                "nota": "Depósito de tercero sin clasificar. Si es ingreso de negocio, debe facturarse. Si es préstamo, reembolso o regalo, necesita documentación.",
            }

        # Retiro a tercero no clasificado
        if tipo == "retiro":
            return {
                "categoria": "retiro",
                "subcategoria": "sin_clasificar",
                "deducible": False,
                "ingreso_gravable": False,
                "riesgo_sat": "ninguno",
                "nota": "Retiro/transferencia a tercero. Normalmente no es deducible.",
            }

        return {
            "categoria": "desconocido",
            "subcategoria": "sin_clasificar",
            "deducible": False,
            "ingreso_gravable": False,
            "riesgo_sat": "medio",
            "nota": "No se pudo clasificar automáticamente.",
        }

    def analizar(self, texto: str, banco: str = "", mes: str = "") -> Dict:
        """
        Análisis completo de estado de cuenta.
        """
        movs = self.parse_tabla(texto)

        # Clasificar cada movimiento
        for m in movs:
            cat = self.clasificar_movimiento(m)
            m.update(
                {
                    "categoria": cat["categoria"],
                    "subcategoria": cat["subcategoria"],
                    "potencial_deducible": cat["deducible"],
                    "ingreso_gravable": cat["ingreso_gravable"],
                    "riesgo_sat": cat["riesgo_sat"],
                    "nota_fiscal": cat["nota"],
                }
            )

        # Agrupar por categoría
        depositos_terceros = [m for m in movs if m["categoria"] == "deposito_tercero"]
        transferencias_propias = [
            m for m in movs if m["categoria"] == "transferencia_propia"
        ]
        gastos_deducibles = [m for m in movs if m["categoria"] == "gasto_deducible"]
        gastos_personales = [m for m in movs if m["categoria"] == "gasto_personal"]
        ingresos_familiares = [m for m in movs if m["categoria"] == "ingreso_familiar"]

        # Calcular totales
        total_depositos = sum(m["monto"] for m in movs if m["tipo"] == "deposito")
        total_retiros = sum(m["monto"] for m in movs if m["tipo"] == "retiro")
        total_terceros = sum(m["monto"] for m in depositos_terceros)
        total_transferencias_propias = sum(m["monto"] for m in transferencias_propias)
        total_potencial_deducible = sum(m["monto"] for m in gastos_deducibles)
        total_personal = sum(m["monto"] for m in gastos_personales)
        total_familiares = sum(m["monto"] for m in ingresos_familiares)

        # Impacto fiscal estimado
        # Si los depósitos de terceros SON ingresos gravables
        iva_potencial = total_terceros * 0.16
        isr_potencial = total_terceros * 0.30

        # Si logran CFDIs de deducciones
        iva_acreditable = total_potencial_deducible * 0.16

        self.resumen = {
            "banco": banco,
            "mes": mes,
            "total_movimientos": len(movs),
            "totales": {
                "depositos": round(total_depositos, 2),
                "retiros": round(total_retiros, 2),
                "saldo_neto": round(total_depositos - total_retiros, 2),
                "terceros_sin_clasificar": round(total_terceros, 2),
                "transferencias_propias": round(total_transferencias_propias, 2),
                "gastos_potencial_deducibles": round(total_potencial_deducible, 2),
                "gastos_personales": round(total_personal, 2),
                "ingresos_familiares": round(total_familiares, 2),
            },
            "impacto_fiscal": {
                "si_terceros_son_ingresos": {
                    "base_gravable": round(total_terceros, 2),
                    "iva_trasladado": round(iva_potencial, 2),
                    "isr_estimado": round(isr_potencial, 2),
                    "total_impuesto": round(iva_potencial + isr_potencial, 2),
                },
                "deducciones_detectadas": {
                    "monto_gastos_sin_cfdi": round(total_potencial_deducible, 2),
                    "iva_acreditable_si_cfdi": round(iva_acreditable, 2),
                    "nota": "Estos gastos NO reducen impuestos sin CFDIs reales",
                },
            },
            "riesgos_detectados": [
                f"{len(depositos_terceros)} depósitos de terceros sin explicar por ${total_terceros:,.2f}",
                f"El SAT puede considerarlos ingresos omitidos si no se documentan",
                "Necesita: contratos de préstamo, reembolso, o facturación",
            ],
            "recomendaciones": [
                "1. Documentar cada depósito de tercero (préstamo, reembolso, regalo)",
                "2. Obtener CFDIs de gastos deducibles si existen",
                "3. Clasificar transferencias propias vs. ingresos reales",
                "4. Considerar suspensión temporal si no hay actividad futura",
            ],
            "movimientos_analizados": movs,
        }

        return self.resumen


def analizar_texto_estado_cuenta(texto: str, banco: str = "", mes: str = "") -> Dict:
    """Entry point rápido."""
    analyzer = EstadoCuentaAnalyzer()
    return analyzer.analizar(texto, banco, mes)
