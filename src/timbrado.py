"""
FiscoMind - Módulo de Timbrado y Cancelación CFDI
Usa el servicio gratuito del SAT (satcfdi library)
Requiere secure_vault para credenciales FIEL encriptadas
"""

import os
import json
from datetime import datetime, date
from typing import Dict, List, Optional
from pathlib import Path

HAS_VAULT = False
try:
    from secure_vault import Vault

    HAS_VAULT = True
except ImportError:
    pass


class TimbradoSAT:
    """
    Maneja timbrado y cancelación de CFDI usando el portal gratuito del SAT.
    Requiere FIEL (.cer + .key + password) configurada en el vault encriptado.
    """

    def __init__(self, rfc: str, vault_dir: str = None):
        self.rfc = rfc
        self.vault_dir = vault_dir or os.environ.get("VAULT_DIR", "/app/credentials")
        self._sat = None
        self._signer = None
        self._vault = Vault() if HAS_VAULT else None

    def _load_fiel(self):
        """Carga credenciales FIEL desde vault encriptado"""
        if not HAS_VAULT or not self._vault:
            return None

        try:
            from satcfdi.models import Signer

            password = self._vault.get_password("fiel_sat")
            key_data = self._vault.decrypt_to_memory("fiel_key")
            cer_data = self._vault.decrypt_to_memory("fiel_cer")

            signer = Signer.load(
                certificate=cer_data, key=key_data, password=password.encode()
            )
            return signer

        except Exception as e:
            print(f"Error cargando FIEL: {e}")
            return None

    def _get_sat(self):
        """Obtiene instancia del SAT connector"""
        if self._sat is None:
            signer = self._load_fiel()
            if signer:
                from satcfdi.pacs.sat import SAT

                self._sat = SAT(signer=signer)
        return self._sat

    def timbrar(self, datos_factura: Dict) -> Dict:
        """
        Genera y timbre un CFDI 4.0 usando el SAT.
        """
        try:
            sat = self._get_sat()
            if not sat:
                return {
                    "status": "error",
                    "message": "No se pudo conectar al SAT. Verifica FIEL.",
                }

            comprobante = self._crear_comprobante(datos_factura)
            resultado = sat.stamp(comprobante)

            return {
                "status": "success",
                "uuid": resultado.uuid,
                "fecha_timbrado": resultado.fecha
                if hasattr(resultado, "fecha")
                else str(datetime.now()),
                "no_certificado_sat": getattr(resultado, "no_certificado_sat", ""),
            }

        except Exception as e:
            return {"status": "error", "message": f"Error en timbrado: {str(e)}"}

    def _crear_comprobante(self, datos: Dict):
        """Crea objeto Comprobante para timbrado"""
        from satcfdi.create.cfd.cfdi40 import Comprobante, Concepto, Emisor, Receptor

        emisor_data = datos.get("emisor", {})
        receptor_data = datos.get("receptor", {})
        conceptos_data = datos.get("conceptos", [])

        emisor = Emisor(
            rfc=emisor_data.get("rfc"),
            nombre=emisor_data.get("nombre"),
            regimen_fiscal=emisor_data.get("regimen", "601"),
        )

        receptor = Receptor(
            rfc=receptor_data.get("rfc"),
            nombre=receptor_data.get("nombre"),
            uso_cfdi=receptor_data.get("uso_cfdi", "G03"),
        )

        conceptos = []
        subtotal = 0
        for c in conceptos_data:
            cantidad = c.get("cantidad", 1)
            valor_unitario = c.get("valor_unitario", 0)
            subtotal += cantidad * valor_unitario

            concepto = Concepto(
                clave_prod_serv=c.get("clave_prod", "01010101"),
                clave_unidad=c.get("clave_unidad", "H87"),
                descripcion=c.get("descripcion", ""),
                cantidad=cantidad,
                valor_unitario=valor_unitario,
            )
            conceptos.append(concepto)

        total = datos.get("total", subtotal)

        comp = Comprobante(
            emisor=emisor,
            receptor=receptor,
            conceptos=conceptos,
            lugar_expedicion=datos.get("lugar_expedicion", "63000"),
            serie=datos.get("serie", "A"),
            folio=datos.get("folio", ""),
            forma_pago=datos.get("forma_pago", "03"),
            metodo_pago=datos.get("metodo_pago", "PUE"),
            moneda=datos.get("moneda", "MXN"),
            tipo_de_comprobante="I",
            exportacion="01",
            fecha=datetime.now(),
        )

        return comp

    def cancelar(self, uuid: str, motivo: str = "02") -> Dict:
        """Cancela un CFDI usando el servicio gratuito del SAT."""
        try:
            from satcfdi.create.cancela.cancelacion import Cancelacion
            from satcfdi.pacs import CancelReason

            sat = self._get_sat()
            if not sat:
                return {
                    "status": "error",
                    "message": "No se pudo conectar al SAT. Verifica FIEL.",
                }

            reason_map = {
                "01": CancelReason.by_selection,
                "02": CancelReason.substitution,
                "03": CancelReason.transferred,
                "04": CancelReason.not_applicable,
            }
            reason = reason_map.get(motivo, CancelReason.substitution)

            cancelacion = Cancelacion(rfc=self.rfc, folios=[uuid], reason=reason)

            resultado = sat.cancel_comprobante(cancelacion)

            return {
                "status": "success",
                "uuid": uuid,
                "mensaje": "CFDI cancelado correctamente",
                "fecha_cancelacion": datetime.now().isoformat(),
            }

        except Exception as e:
            return {"status": "error", "message": f"Error en cancelación: {str(e)}"}

    def validar_estado_cfdi(self, uuid: str) -> Dict:
        """Consulta el estado de un CFDI en el SAT"""
        try:
            from satcfdi.cfdi import CFDI

            sat = self._get_sat()
            if not sat:
                return {"status": "error", "message": "SAT no disponible"}

            # Create minimal CFDI object for status check
            cfdi = CFDI(uuid=uuid)
            estado = sat.status(cfdi=cfdi)

            return {
                "status": "success",
                "uuid": uuid,
                "estado": estado.get("estado", "desconocido"),
                "valido": estado.get("estado") == "Vigente",
            }

        except Exception as e:
            return {"status": "error", "message": f"Error: {str(e)}"}

        except Exception as e:
            return {"status": "error", "message": f"Error: {str(e)}"}


class FacturaBuilder:
    """Helper para construir facturas CFDI 4.0"""

    USOS_CFDI = {
        "G01": "Adquisición de mercancias",
        "G02": "Devoluciones, descuentos o bonificaciones",
        "G03": "Gastos en general",
        "G04": "Por definir",
        "I01": "Construcciones",
        "I02": "Mobiliario y equipo de oficina",
        "I03": "Equipo de transporte",
        "I04": "Equipo de cómputo y accesorios",
        "I05": "Dados, troqueles, moldes",
        "I06": "Refacciones y accesorios",
        "I07": "Otros activos",
        "D01": "Honarios médicos",
        "D02": "Gastos médicos",
        "D03": "Gastos funerarios",
        "D04": "Donativos",
        "D05": "Intereses reales",
        "S01": "Sin efectos fiscales",
    }

    REGIMENES_FISCALES = {
        "601": "General de Ley Personas Morales",
        "603": "Personas Morales con fines no lucrativos",
        "605": "Sueldos y salarios",
        "606": "Arrendamiento",
        "608": "Otros ingresos",
        "610": "Residentes en el extranjero",
        "612": "Consolidación fiscal",
        "620": "Sociedades cooperativas",
        "621": "Actividades agrícolas",
        "622": "Actividades ganaderas",
        "623": "Actividades silvícolas",
        "624": "Actividad pesquera",
        "625": "Incorporación fiscal",
    }

    FORMAS_PAGO = {
        "01": "Efectivo",
        "02": "Cheque nominativo",
        "03": "Transferencia electrónica",
        "04": "Tarjeta de crédito",
        "05": "Monedero electrónico",
        "28": "Por definir",
    }

    METODOS_PAGO = {
        "PUE": "Pago en una sola exhibición",
        "PPD": "Pago en parcialidades o diferido",
    }

    @staticmethod
    def build_factura_base(
        emisor_rfc: str,
        emisor_nombre: str,
        receptor_rfc: str,
        receptor_nombre: str,
        conceptos: List[Dict],
        total: float,
        uso_cfdi: str = "G03",
    ) -> Dict:
        """Construye estructura base para timbrar"""
        return {
            "emisor": {"rfc": emisor_rfc, "nombre": emisor_nombre, "regimen": "601"},
            "receptor": {
                "rfc": receptor_rfc,
                "nombre": receptor_nombre,
                "uso_cfdi": uso_cfdi,
            },
            "conceptos": conceptos,
            "forma_pago": "03",
            "metodo_pago": "PUE",
            "moneda": "MXN",
            "subtotal": total,
            "total": total,
        }
