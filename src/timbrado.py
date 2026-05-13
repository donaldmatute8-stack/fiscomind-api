"""
FiscoMind - Módulo de Timbrado y Cancelación CFDI
Usa el servicio gratuito del SAT (satcfdi library)
"""

import os
import json
from datetime import datetime, date
from typing import Dict, List, Optional
from pathlib import Path


class TimbradoSAT:
    """
    Maneja timbrado y cancelación de CFDI usando el portal gratuito del SAT.
    Requiere FIEL (.cer + .key + password) configurada en el vault.
    """

    def __init__(self, rfc: str, vault_dir: str = None):
        self.rfc = rfc
        self.vault_dir = vault_dir or f"/app/data/users/{rfc.lower()}/vault"
        self._sat = None
        self._fiel = None

    def _load_fiel(self):
        """Carga credenciales FIEL desde vault encriptado"""
        try:
            from satcfdi.pacs.sat import Certificate

            # Buscar archivos FIEL en vault
            cer_path = Path(self.vault_dir) / "fiel.cer"
            key_path = Path(self.vault_dir) / "fiel.key"
            password = os.environ.get("FIEL_PASSWORD", "")

            if not cer_path.exists() or not key_path.exists():
                return None

            fiel = Certificate.from_pkcs12(
                pkcs12_file=str(cer_path), key_file=str(key_path), password=password
            )
            return fiel
        except Exception as e:
            print(f"Error cargando FIEL: {e}")
            return None

    def _get_sat(self):
        """Obtiene instancia del SAT connector"""
        if self._sat is None:
            try:
                from satcfdi.pacs.sat import SAT

                fiel = self._load_fiel()
                if fiel:
                    self._sat = SAT(fiel=fiel)
                else:
                    # Intentar usar connector existente
                    try:
                        from sat_connector_real import SATConnectorReal

                        connector = SATConnectorReal(rfc=self.rfc)
                        if connector._is_connected:
                            # Usar el SAT del connector si está disponible
                            # Esto depende de cómo esté implementado SATConnectorReal
                            pass
                    except:
                        pass
            except Exception as e:
                print(f"Error creando SAT: {e}")
        return self._sat

    def timbrar(self, datos_factura: Dict) -> Dict:
        """
        Genera y timbre un CFDI 4.0 usando el SAT.

        datos_factura = {
            "emisor": {
                "rfc": "XAXX010101000",
                "nombre": "Nombre Emisor",
                "regimen": "601"  # Régimen fiscal
            },
            "receptor": {
                "rfc": "XEXX010101000",
                "nombre": "Nombre Receptor",
                "uso_cfdi": "G03"  # Uso de CFDI
            },
            "conceptos": [
                {
                    "clave_prod": "01010101",
                    "clave_unidad": "H87",
                    "descripcion": "Producto o servicio",
                    "cantidad": 1,
                    "valor_unitario": 1000.00
                }
            ],
            "forma_pago": "01",  # Efectivo
            "metodo_pago": "PUE",  # Pago en una sola exhibición
            "moneda": "MXN"
        }
        """
        try:
            sat = self._get_sat()
            if not sat:
                return {
                    "status": "error",
                    "message": "No se pudo conectar al SAT. Verifica FIEL.",
                }

            # Crear comprobante
            comprobante = self._crear_comprobante(datos_factura)

            # Timbrar
            resultado = sat.stamp(comprobante)

            return {
                "status": "success",
                "uuid": resultado.uuid,
                "fecha_timbrado": resultado.fecha_timbrado.isoformat()
                if hasattr(resultado, "fecha_timbrado")
                else str(datetime.now()),
                "xml": str(resultado),
                "no_certificado_sat": resultado.no_certificado_sat
                if hasattr(resultado, "no_certificado_sat")
                else "",
            }

        except Exception as e:
            return {"status": "error", "message": f"Error en timbrado: {str(e)}"}

    def _crear_comprobante(self, datos: Dict):
        """Crea objeto Comprobante para timbrado"""
        from satcfdi.create import Comprobante, Concepto, Emisor, Receptor

        emisor_data = datos.get("emisor", {})
        receptor_data = datos.get("receptor", {})
        conceptos_data = datos.get("conceptos", [])

        # Crear emisor
        emisor = Emisor(
            rfc=emisor_data.get("rfc"),
            nombre=emisor_data.get("nombre"),
            regimen_fiscal=emisor_data.get("regimen", "601"),
        )

        # Crear receptor
        receptor = Receptor(
            rfc=receptor_data.get("rfc"),
            nombre=receptor_data.get("nombre"),
            uso_cfdi=receptor_data.get("uso_cfdi", "G03"),
        )

        # Crear conceptos
        conceptos = []
        for c in conceptos_data:
            concepto = Concepto(
                clave_prod_serv=c.get("clave_prod", "01010101"),
                clave_unidad=c.get("clave_unidad", "H87"),
                descripcion=c.get("descripcion", ""),
                cantidad=c.get("cantidad", 1),
                valor_unitario=c.get("valor_unitario", 0),
            )
            conceptos.append(concepto)

        # Crear comprobante
        comp = Comprobante(
            serie=datos.get("serie", "A"),
            folio=datos.get("folio", ""),
            fecha=datos.get("fecha", datetime.now().isoformat()),
            emisor=emisor,
            receptor=receptor,
            conceptos=conceptos,
            forma_pago=datos.get("forma_pago", "01"),
            metodo_pago=datos.get("metodo_pago", "PUE"),
            moneda=datos.get("moneda", "MXN"),
            tipo_comprobante=datos.get("tipo", "I"),  # Ingreso
            subtotal=datos.get(
                "subtotal",
                sum(
                    c.get("valor_unitario", 0) * c.get("cantidad", 1)
                    for c in conceptos_data
                ),
            ),
            total=datos.get(
                "total",
                sum(
                    c.get("valor_unitario", 0) * c.get("cantidad", 1)
                    for c in conceptos_data
                ),
            ),
        )

        return comp

    def cancelar(self, uuid: str, motivo: str = "02") -> Dict:
        """
        Cancela un CFDI usando el servicio gratuito del SAT.

        Motivos:
        - "01" = Comprobante emitidas con errores con relación
        - "02" = Comprobante sustituir
        - "03" = Comprobante trasladadas
        - "04" = Comprobante pagadas en una única exhibición
        """
        try:
            sat = self._get_sat()
            if not sat:
                return {
                    "status": "error",
                    "message": "No se pudo conectar al SAT. Verifica FIEL.",
                }

            # Cancelar usando el SAT
            resultado = sat.cancel_comprobante(uuid=uuid, rfc=self.rfc)

            return {
                "status": "success",
                "uuid": uuid,
                "mensaje": "CFDI cancelado correctamente",
                "fecha_cancelacion": datetime.now().isoformat(),
            }

        except Exception as e:
            return {"status": "error", "message": f"Error en cancelación: {str(e)}"}

    def solicitar_cancelacion(self, uuid: str, rfc_receptor: str) -> Dict:
        """
        Solicita cancelación (requiere aceptación del receptor según reglas SAT)
        """
        try:
            sat = self._get_sat()
            if not sat:
                return {"status": "error", "message": "No se pudo conectar al SAT"}

            # Usar accept_reject para solicitar
            # Esto envía una solicitud al buzón tributario del receptor
            resultado = sat.accept_reject(
                uuid=uuid, rfc=self.rfc, action="solicitar_cancelacion"
            )

            return {
                "status": "success",
                "uuid": uuid,
                "mensaje": "Solicitud enviada. Espera aceptación del receptor.",
                "fecha_solicitud": datetime.now().isoformat(),
            }

        except Exception as e:
            return {"status": "error", "message": f"Error: {str(e)}"}

    def validar_estado_cfdi(self, uuid: str) -> Dict:
        """
        Consulta el estado de un CFDI en el SAT
        """
        try:
            sat = self._get_sat()
            if not sat:
                return {"status": "error", "message": "SAT no disponible"}

            estado = sat.status(uuid=uuid)

            return {
                "status": "success",
                "uuid": uuid,
                "estado": str(estado),
                "valido": estado == "Vigente" or estado == "1",
            }

        except Exception as e:
            return {"status": "error", "message": f"Error: {str(e)}"}


class FacturaBuilder:
    """
    Helper para construir facturas CFDI 4.0
    """

    # Uso CFDI (Catálogo SAT)
    USOS_CFDI = {
        "G01": "Adquisición de mercancias",
        "G02": "Devoluciones, descuentos o bonificaciones",
        "G03": "Gastos en general",
        "I01": "Construcciones",
        "I02": "Mobiliario y equipo de oficina por inversiones",
        "I03": "Equipo de transporte",
        "I04": "Equipo de cómputo y accesorios",
        "I05": "Dados, troqueles, moldes, herramientas",
        "I06": "Refacciones y accesorios",
        "I07": "Otros activos",
        "D01": "Honarios médicos",
        "D02": "Gastos médicos por incapacidad",
        "D03": "Gastos funerarios",
        "D04": "Donativos",
        "D05": "Intereses reales efectivamente devengados",
        "D06": "Aportaciones voluntarias al SAR",
        "D07": "Premios por plan de retiro",
        "D08": "Aportaciones patronales al SAR",
        "D09": "Primas por seguros de gastos médicos",
        "D10": "Gastos de transportación escolar",
        "S01": "Sin efectos fiscales",
    }

    # Régimen fiscal (Catálogo SAT)
    REGIMENES_FISCALES = {
        "601": "General de Ley Personas Morales",
        "603": "Personas Morales con fines no lucrativos",
        "605": "Sueldos y salarios asimilados a ingresos",
        "606": "Arrendamiento",
        "608": "Otros ingresos",
        "610": "Residentes en el extranjero",
        "612": "Consolidación fiscal",
        "620": "Sociedades cooperativas de producción",
        "621": "Actividades agrícolas",
        "622": "Actividades ganaderas",
        "623": "Actividades silvícolas",
        "624": "Actividad pesquera",
        "625": "Incorporación fiscal",
    }

    # Forma de pago
    FORMAS_PAGO = {
        "01": "Efectivo",
        "02": "Cheque nominativo",
        "03": "Transferencia electrónica de fondos",
        "04": "Tarjeta de crédito",
        "05": "Monedero electrónico",
        "06": "Dinero electrónico",
        "08": "Vales de despensa",
        "28": "Por definir",
    }

    # Método de pago
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
            "forma_pago": "03",  # Transferencia
            "metodo_pago": "PUE",
            "moneda": "MXN",
            "subtotal": total,
            "total": total,
        }


# Ejemplo de uso
if __name__ == "__main__":
    builder = FacturaBuilder()

    factura = builder.build_factura_base(
        emisor_rfc="MUTM8610091NA",
        emisor_nombre="Marco Arturo Muñoz del Toro",
        receptor_rfc="XEXX010101000",
        receptor_nombre="Empresa Ejemplo S.A. de C.V.",
        conceptos=[
            {
                "descripcion": "Servicio de asesoría fiscal",
                "valor_unitario": 5000.00,
                "cantidad": 1,
            }
        ],
        total=5000.00,
    )

    print("Factura lista para timbrar:")
    print(json.dumps(factura, indent=2, ensure_ascii=False))
