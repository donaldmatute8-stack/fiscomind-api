from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any

class CFDIStatus(Enum):
    VIGENTE = "Vigente"
    CANCELADO = "Cancelado"
    CANC_S_EFECTOS = "Cancelado sin efectos"

class CFDIType(Enum):
    RECIBIDO = "recibidos"
    EMITIDO = "emitidos"

@dataclass
class SATAuthCredentials:
    rfc: str
    password: Optional[str] = None
    efirma_path: Optional[str] = None
    efirma_key: Optional[str] = None

@dataclass
class CFDIModel:
    folio: str
    emisor: str
    receptor: str
    monto: float
    fecha: datetime
    status: CFDIStatus
    xml_content: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ComplianceOpinion:
    rfc: str
    status: str  # "Positiva" or "Negativa"
    issue_date: datetime
    pending_obligations: List[str]
    is_compliant: bool
