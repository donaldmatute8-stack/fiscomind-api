import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class CFDIItem:
    description: str
    quantity: float
    value: float

@dataclass
class CFDIData:
    rfc_emisor: str
    rfc_receptor: str
    total: float
    moneda: str
    impuestos: float
    conceptos: List[CFDIItem]

def parse_cfdi(xml_path: str) -> Optional[CFDIData]:
    """
    Parses a CFDI 4.0 XML file and extracts key financial and tax data.
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        # CFDI namespaces
        ns = {'cfdi': 'http://www.sat.gob.mx/cfd/4'}
        
        # Extract Issuer and Receiver RFCs
        emisor = root.find('cfdi:Emisor', ns)
        receptor = root.find('cfdi:Receptor', ns)
        
        rfc_emisor = emisor.attrib.get('Rfc') if emisor is not None else "Unknown"
        rfc_receptor = receptor.attrib.get('Rfc') if receptor is not None else "Unknown"
        
        # Total and Currency
        total = float(root.attrib.get('Total', 0))
        moneda = root.attrib.get('Moneda', 'MXN')
        
        # Taxes (Simplified: Sum of all Traslados)
        impuestos = 0.0
        complemento = root.find('cfdi:Complemento', ns)
        # Note: In a real CFDI 4.0, taxes are usually in Impuestos -> Traslados
        imp_node = root.find('cfdi:Impuestos', ns)
        if imp_node is not None:
            traslados = imp_node.find('cfdi:Traslados', ns)
            if traslados is not None:
                for t in traslados.findall('cfdi:Traslado', ns):
                    impuestos += float(t.attrib.get('Importe', 0))

        # Concepts
        conceptos = []
        concepts_node = root.find('cfdi:Conceptos', ns)
        if concepts_node is not None:
            for c in concepts_node.findall('cfdi:Concepto', ns):
                conceptos.append(CFDIItem(
                    description=c.attrib.get('ClaveProdServ', 'N/A') + " " + c.attrib.get('Descripcion', ''),
                    quantity=float(c.attrib.get('Cantidad', 0)),
                    value=float(c.attrib.get('ValorUnitario', 0))
                ))
                
        return CFDIData(
            rfc_emisor=rfc_emisor,
            rfc_receptor=rfc_receptor,
            total=total,
            moneda=moneda,
            impuestos=impuestos,
            conceptos=conceptos
        )
    except Exception as e:
        print(f"Error parsing XML {xml_path}: {e}")
        return None

if __name__ == "__main__":
    # Example usage for testing
    import sys
    if len(sys.argv) > 1:
        data = parse_cfdi(sys.argv[1])
        if data:
            print(f"RFC Emisor: {data.rfc_emisor}")
            print(f"RFC Receptor: {data.rfc_receptor}")
            print(f"Total: {data.total} {data.moneda}")
            print(f"Impuestos: {data.impuestos}")
            for item in data.conceptos:
                print(f"- {item.description}: {item.value}")
