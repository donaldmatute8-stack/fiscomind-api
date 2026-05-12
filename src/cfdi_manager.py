"""
CFDI Manager - Extract, generate PDF, and manage CFDIs
Handles XML extraction, PDF generation, and invoice creation
"""
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import json
import base64
import zipfile
import io

@dataclass
class CFDIData:
    """Complete CFDI data structure"""
    uuid: str
    emisor_nombre: str
    emisor_rfc: str
    emisor_regimen: str
    receptor_nombre: str
    receptor_rfc: str
    receptor_uso_cfdi: str
    total: float
    subtotal: float
    iva: float
    fecha_emision: str
    fecha_certificacion: str
    serie: str
    folio: str
    tipo: str  # I=Ingreso, E=Egreso, N=Nómina, etc
    forma_pago: str
    metodo_pago: str
    moneda: str
    conceptos: List[Dict]
    xml_content: str
    estado: str  # 1=Vigente, 0=Cancelado
    fecha_cancelacion: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            'uuid': self.uuid,
            'emisor': {
                'nombre': self.emisor_nombre,
                'rfc': self.emisor_rfc,
                'regimen': self.emisor_regimen
            },
            'receptor': {
                'nombre': self.receptor_nombre,
                'rfc': self.receptor_rfc,
                'uso_cfdi': self.receptor_uso_cfdi
            },
            'totales': {
                'subtotal': self.subtotal,
                'iva': self.iva,
                'total': self.total
            },
            'fechas': {
                'emision': self.fecha_emision,
                'certificacion': self.fecha_certificacion,
                'cancelacion': self.fecha_cancelacion
            },
            'comprobante': {
                'serie': self.serie,
                'folio': self.folio,
                'tipo': self.tipo,
                'forma_pago': self.forma_pago,
                'metodo_pago': self.metodo_pago,
                'moneda': self.moneda
            },
            'conceptos': self.conceptos,
            'estado': self.estado,
            'estado_str': 'Vigente' if self.estado == '1' else 'Cancelado'
        }


class CFDIManager:
    """Manager for CFDI operations"""
    
    # XML Namespaces
    NS = {
        'cfdi': 'http://www.sat.gob.mx/cfd/4',
        'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital',
        'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
    }
    
    def __init__(self, data_dir: str = '/Users/bullslab/.openclaw/agents/fisco-workspace/data/cfdis'):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.xml_dir = self.data_dir / 'xml'
        self.pdf_dir = self.data_dir / 'pdf'
        self.xml_dir.mkdir(exist_ok=True)
        self.pdf_dir.mkdir(exist_ok=True)
    
    def parse_xml(self, xml_content: str) -> CFDIData:
        """Parse CFDI XML and extract all data"""
        root = ET.fromstring(xml_content)
        
        # Get Timbre Fiscal Digital
        tfd = root.find('.//tfd:TimbreFiscalDigital', self.NS)
        uuid = tfd.get('UUID', '') if tfd is not None else ''
        
        # Get Emisor
        emisor = root.find('.//cfdi:Emisor', self.NS)
        emisor_nombre = emisor.get('Nombre', '') if emisor is not None else ''
        emisor_rfc = emisor.get('Rfc', '') if emisor is not None else ''
        emisor_regimen = emisor.get('RegimenFiscal', '') if emisor is not None else ''
        
        # Get Receptor
        receptor = root.find('.//cfdi:Receptor', self.NS)
        receptor_nombre = receptor.get('Nombre', '') if receptor is not None else ''
        receptor_rfc = receptor.get('Rfc', '') if receptor is not None else ''
        receptor_uso = receptor.get('UsoCFDI', '') if receptor is not None else ''
        
        # Get Totals
        total = float(root.get('Total', '0'))
        subtotal = float(root.get('SubTotal', '0'))
        
        # Calculate IVA from Impuestos
        impuestos = root.find('.//cfdi:Impuestos[@TotalImpuestosTrasladados]', self.NS)
        iva = float(impuestos.get('TotalImpuestosTrasladados', '0')) if impuestos is not None else 0.0
        
        # Get Fechas
        fecha_emision = root.get('Fecha', '')
        fecha_cert = tfd.get('FechaTimbrado', '') if tfd is not None else ''
        
        # Get Comprobante data
        serie = root.get('Serie', '')
        folio = root.get('Folio', '')
        tipo = root.get('TipoDeComprobante', 'I')
        forma_pago = root.get('FormaPago', '99')
        metodo_pago = root.get('MetodoPago', 'PUE')
        moneda = root.get('Moneda', 'MXN')
        
        # Get Conceptos
        conceptos = []
        for concepto in root.findall('.//cfdi:Concepto', self.NS):
            conceptos.append({
                'descripcion': concepto.get('Descripcion', ''),
                'cantidad': float(concepto.get('Cantidad', '0')),
                'unidad': concepto.get('Unidad', ''),
                'valor_unitario': float(concepto.get('ValorUnitario', '0')),
                'importe': float(concepto.get('Importe', '0')),
                'clave_prod_serv': concepto.get('ClaveProdServ', ''),
                'clave_unidad': concepto.get('ClaveUnidad', '')
            })
        
        return CFDIData(
            uuid=uuid,
            emisor_nombre=emisor_nombre,
            emisor_rfc=emisor_rfc,
            emisor_regimen=emisor_regimen,
            receptor_nombre=receptor_nombre,
            receptor_rfc=receptor_rfc,
            receptor_uso_cfdi=receptor_uso,
            total=total,
            subtotal=subtotal,
            iva=iva,
            fecha_emision=fecha_emision,
            fecha_certificacion=fecha_cert,
            serie=serie,
            folio=folio,
            tipo=tipo,
            forma_pago=forma_pago,
            metodo_pago=metodo_pago,
            moneda=moneda,
            conceptos=conceptos,
            xml_content=xml_content,
            estado='1'  # Default to vigente
        )
    
    def extract_from_sat_package(self, zip_base64: str) -> List[CFDIData]:
        """Extract CFDIs from SAT download package (base64 encoded zip)"""
        cfdis = []
        
        try:
            decoded = base64.b64decode(zip_base64)
            
            with zipfile.ZipFile(io.BytesIO(decoded)) as zf:
                for fname in zf.namelist():
                    if fname.endswith('.xml'):
                        content = zf.read(fname).decode('utf-8')
                        try:
                            cfdi = self.parse_xml(content)
                            cfdis.append(cfdi)
                            # Save XML
                            self.save_xml(cfdi.uuid, content)
                        except Exception as e:
                            print(f"Error parsing {fname}: {e}")
                            
        except Exception as e:
            print(f"Error extracting package: {e}")
            
        return cfdis
    
    def parse_metadata_csv(self, csv_content: str) -> List[Dict]:
        """Parse SAT metadata CSV format"""
        lines = csv_content.strip().split('\n')
        if len(lines) < 2:
            return []
        
        headers = lines[0].split('~')
        records = []
        
        for line in lines[1:]:
            values = line.split('~')
            if len(values) >= 11:
                records.append({
                    'uuid': values[0],
                    'rfc_emisor': values[1],
                    'nombre_emisor': values[2],
                    'rfc_receptor': values[3],
                    'nombre_receptor': values[4],
                    'pac': values[5],
                    'fecha_emision': values[6],
                    'fecha_certificacion': values[7],
                    'monto': values[8],
                    'efecto': values[9],  # P=Pagado, etc
                    'estatus': values[10],  # 1=Vigente, 0=Cancelado
                    'fecha_cancelacion': values[11] if len(values) > 11 else None
                })
        
        return records
    
    def save_xml(self, uuid: str, xml_content: str) -> str:
        """Save XML to file"""
        filepath = self.xml_dir / f"{uuid}.xml"
        filepath.write_text(xml_content, encoding='utf-8')
        return str(filepath)
    
    def save_metadata_json(self, cfdi: CFDIData) -> str:
        """Save CFDI metadata as JSON"""
        filepath = self.xml_dir / f"{cfdi.uuid}.json"
        filepath.write_text(json.dumps(cfdi.to_dict(), indent=2, ensure_ascii=False), encoding='utf-8')
        return str(filepath)
    
    def load_xml(self, uuid: str) -> Optional[str]:
        """Load XML from file"""
        filepath = self.xml_dir / f"{uuid}.xml"
        if filepath.exists():
            return filepath.read_text(encoding='utf-8')
        return None
    
    def get_all_cfdis(self) -> List[Dict]:
        """Get all stored CFDIs"""
        cfdis = []
        for json_file in self.xml_dir.glob('*.json'):
            try:
                data = json.loads(json_file.read_text(encoding='utf-8'))
                cfdis.append(data)
            except:
                pass
        return cfdis
    
    def get_cfdi_by_uuid(self, uuid: str) -> Optional[Dict]:
        """Get single CFDI by UUID"""
        filepath = self.xml_dir / f"{uuid}.json"
        if filepath.exists():
            return json.loads(filepath.read_text(encoding='utf-8'))
        return None
    
    def get_summary(self) -> Dict:
        """Get CFDI summary statistics"""
        cfdis = self.get_all_cfdis()
        
        total_vigentes = sum(1 for c in cfdis if c.get('estado') == '1')
        total_cancelados = sum(1 for c in cfdis if c.get('estado') == '0')
        
        total_ingresos = sum(c['totales']['total'] for c in cfdis if c.get('estado') == '1')
        
        return {
            'total_cfdis': len(cfdis),
            'vigentes': total_vigentes,
            'cancelados': total_cancelados,
            'total_monto': total_ingresos,
            'periodo': self._get_date_range(cfdis)
        }
    
    def _get_date_range(self, cfdis: List[Dict]) -> Dict:
        """Get date range of CFDIs"""
        if not cfdis:
            return {'desde': None, 'hasta': None}
        
        fechas = [c['fechas']['emision'] for c in cfdis if c.get('fechas', {}).get('emision')]
        if not fechas:
            return {'desde': None, 'hasta': None}
        
        fechas_sorted = sorted(fechas)
        return {'desde': fechas_sorted[0], 'hasta': fechas_sorted[-1]}


# Generator for creating new invoices (CFDI)
class CFDIGenerator:
    """Generate new CFDI XML for invoice creation"""
    
    def __init__(self):
        self.template = '''<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante 
    xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.sat.gob.mx/cfd/4 http://www.sat.gob.mx/sitio_internet/cfd/4/cfdv40.xsd"
    Version="4.0"
    Serie="{serie}"
    Folio="{folio}"
    Fecha="{fecha}"
    FormaPago="{forma_pago}"
    NoCertificado="{no_certificado}"
    Certificado="{certificado}"
    SubTotal="{subtotal:.2f}"
    Moneda="{moneda}"
    Total="{total:.2f}"
    TipoDeComprobante="{tipo}"
    MetodoPago="{metodo_pago}"
    LugarExpedicion="{lugar_expedicion}"
    Exportacion="{exportacion}"
    Sello="">
    <cfdi:Emisor Rfc="{emisor_rfc}" Nombre="{emisor_nombre}" RegimenFiscal="{emisor_regimen}"/>
    <cfdi:Receptor Rfc="{receptor_rfc}" Nombre="{receptor_nombre}" DomicilioFiscalReceptor="{receptor_cp}" RegimenFiscalReceptor="{receptor_regimen}" UsoCFDI="{receptor_uso_cfdi}"/>
    <cfdi:Conceptos>
{conceptos_xml}
    </cfdi:Conceptos>
    <cfdi:Impuestos TotalImpuestosTrasladados="{total_iva:.2f}">
        <cfdi:Traslados>
            <cfdi:Traslado Base="{subtotal:.2f}" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="{total_iva:.2f}"/>
        </cfdi:Traslados>
    </cfdi:Impuestos>
</cfdi:Comprobante>'''
    
    def generate_invoice_xml(self, data: Dict) -> str:
        """Generate CFDI XML for a new invoice"""
        
        # Generate conceptos XML
        conceptos_xml = []
        for concepto in data.get('conceptos', []):
            concepto_xml = f'''        <cfdi:Concepto ClaveProdServ="{concepto.get('clave', '01010101')}" 
            NoIdentificacion="{concepto.get('id', '')}" 
            Cantidad="{concepto.get('cantidad', 1)}" 
            ClaveUnidad="{concepto.get('unidad', 'E48')}" 
            Unidad="{concepto.get('unidad_desc', 'Servicio')}" 
            Descripcion="{concepto.get('descripcion', '')}" 
            ValorUnitario="{concepto.get('precio', 0):.2f}" 
            Importe="{concepto.get('importe', 0):.2f}"
            ObjetoImp="{concepto.get('objeto_imp', '02')}">
            <cfdi:Impuestos>
                <cfdi:Traslados>
                    <cfdi:Traslado Base="{concepto.get('importe', 0):.2f}" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="{concepto.get('iva', 0):.2f}"/>
                </cfdi:Traslados>
            </cfdi:Impuestos>
        </cfdi:Concepto>'''
            conceptos_xml.append(concepto_xml)
        
        subtotal = data.get('subtotal', 0)
        iva = data.get('iva', subtotal * 0.16)
        total = subtotal + iva
        
        return self.template.format(
            serie=data.get('serie', 'F'),
            folio=data.get('folio', '0001'),
            fecha=datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
            forma_pago=data.get('forma_pago', '99'),
            no_certificado=data.get('no_certificado', ''),
            certificado=data.get('certificado', ''),
            subtotal=subtotal,
            moneda=data.get('moneda', 'MXN'),
            total=total,
            tipo=data.get('tipo', 'I'),
            metodo_pago=data.get('metodo_pago', 'PUE'),
            lugar_expedicion=data.get('lugar_expedicion', '01000'),
            exportacion=data.get('exportacion', '01'),
            emisor_rfc=data.get('emisor_rfc', ''),
            emisor_nombre=data.get('emisor_nombre', ''),
            emisor_regimen=data.get('emisor_regimen', '601'),
            receptor_rfc=data.get('receptor_rfc', ''),
            receptor_nombre=data.get('receptor_nombre', ''),
            receptor_cp=data.get('receptor_cp', '01000'),
            receptor_regimen=data.get('receptor_regimen', '601'),
            receptor_uso_cfdi=data.get('receptor_uso_cfdi', 'G03'),
            conceptos_xml='\n'.join(conceptos_xml),
            total_iva=iva
        )


if __name__ == '__main__':
    manager = CFDIManager()
    print(f"CFDI Manager initialized at {manager.data_dir}")
    print(f"XML storage: {manager.xml_dir}")
    print(f"PDF storage: {manager.pdf_dir}")
