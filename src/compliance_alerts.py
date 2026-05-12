from datetime import datetime, date
from typing import List, Dict

class ComplianceAlerts:
    """
    Tracks Mexican fiscal deadlines for different regimes.
    """
    def __init__(self):
        # Simplified obligations mapping
        self.obligations = {
            "mensual": [
                {"name": "Declaración Provisional ISR", "day": 17, "desc": "Presentación de pagos provisionales mensuales."},
                {"name": "Declaración IVA", "day": 17, "desc": "Declaración y pago del Impuesto al Valor Agregado."},
            ],
            "bimestral": [
                {"name": "Declaración Bimestral (RESICO)", "day": 17, "desc": "Declaración de ingresos y pagos bimestrales."},
            ],
            "anual": [
                {"name": "Declaración Anual Persona Física", "month": 4, "day": 30, "desc": "Cierre fiscal anual."},
                {"name": "Declaración Anual Persona Moral", "month": 3, "day": 31, "desc": "Cierre fiscal anual corporativo."},
            ]
        }

    def get_upcoming_alerts(self, current_date: date = None) -> List[Dict]:
        if current_date is None:
            current_date = date.today()
            
        alerts = []
        
        # Monthly check
        for obl in self.obligations["mensual"]:
            # Estimate next occurrence
            # Simplified: if today is before the 17th, alert for this month. Otherwise, next month.
            if current_date.day <= 17:
                alerts.append({
                    "date": f"{current_date.year}-{current_date.month:02d}-{obl['day']}",
                    "obligation": obl["name"],
                    "description": obl["desc"]
                })
        
        # Annual check
        for obl in self.obligations["anual"]:
            # Simplified: if current date is before the deadline
            deadline = date(current_date.year, obl["month"], obl["day"])
            if current_date < deadline:
                alerts.append({
                    "date": f"{deadline.year}-{deadline.month:02d}-{deadline.day:02d}",
                    "obligation": obl["name"],
                    "description": obl["desc"]
                })
                
        return alerts

if __name__ == "__main__":
    ca = ComplianceAlerts()
    print("Alertas de cumplimiento próximas:")
    for alert in ca.get_upcoming_alerts():
        print(f"📅 {alert['date']} - {alert['obligation']}: {alert['description']}")
