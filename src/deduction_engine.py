from typing import List, Dict
from dataclasses import dataclass

@dataclass
class DeductionSuggestion:
    concept: str
    amount: float
    reason: str
    confidence: float # 0.0 to 1.0

class DeductionEngine:
    """
    Analyzes expenses based on Mexican Income Tax Law (LISR) rules.
    """
    def __init__(self):
        # Simplified rules engine: Keyword mapping to deduction potential
        self.rules = {
            "gasolina": {"category": "Transportation", "deductible": True, "note": "Strictly deductible if paid by electronic means."},
            "papeleria": {"category": "Office Supplies", "deductible": True, "note": "Standard office expense."},
            "internet": {"category": "Utilities", "deductible": True, "note": "Deductible as operational expense."},
            "luz": {"category": "Utilities", "deductible": True, "note": "Deductible as operational expense."},
            "renta": {"category": "Real Estate", "deductible": True, "note": "Deductible with valid lease agreement."},
            "software": {"category": "Tech", "deductible": True, "note": "Deductible as operational tool/asset."},
            "gastos medicos": {"category": "Health", "deductible": True, "note": "Personal deduction: medical expenses (LISR Art. 151)."},
            "hospital": {"category": "Health", "deductible": True, "note": "Personal deduction: hospital expenses."},
            "donativos": {"category": "Charity", "deductible": True, "note": "Deductible donation to authorized entities."},
            "seguros": {"category": "Insurance", "deductible": True, "note": "Deductible health/life insurance premiums."},
            "aportaciones voluntarias": {"category": "Retirement", "deductible": True, "note": "Tax-deductible voluntary contributions to AFRC."},
        }

    def evaluate(self, expense_type: str, amount: float, category: str):
        """
        Quick evaluation for a specific expense.
        Returns a mock result as per main.py expectations.
        """
        # Simplified logic for CLI evaluate call
        is_deductible = False
        reason = "Not recognized as deductible."
        
        cat_lower = category.lower().replace("_", " ").replace("-", " ")
        for keyword, rule in self.rules.items():
            if keyword in cat_lower or keyword.replace(" ", "_") in category.lower() or keyword.replace(" ", "-") in category.lower():
                is_deductible = rule["deductible"]
                reason = rule["note"]
                break
        
        # Simple Mock Result class to avoid changing main.py's print logic
        class EvalResult:
            def __init__(self, is_ded, amt, reas):
                self.is_deductible = is_ded
                self.amount = amt
                self.reason = reas
                
        return EvalResult(is_deductible, amount, reason)

    def analyze_cfdi(self, cfdi_data) -> List[DeductionSuggestion]:
        suggestions = []
        
        for item in cfdi_data.conceptos:
            desc_lower = item.description.lower()
            for keyword, rule in self.rules.items():
                if keyword in desc_lower:
                    suggestions.append(DeductionSuggestion(
                        concept=item.description,
                        amount=item.value * item.quantity,
                        reason=rule["note"],
                        confidence=0.9 if rule["deductible"] else 0.1
                    ))
                    break
        
        if not suggestions:
            # Generic fallback if no keywords match
            suggestions.append(DeductionSuggestion(
                concept="General Expense",
                amount=cfdi_data.total,
                reason="Review manually: No automatic rule match found.",
                confidence=0.3
            ))
            
        return suggestions

if __name__ == "__main__":
    # Mock data for testing
    from cfdi_parser import CFDIData, CFDIItem
    mock_data = CFDIData(
        rfc_emisor="AAA010101AAA", 
        rfc_receptor="BBB020202BBB", 
        total=1500.0, 
        moneda="MXN", 
        impuestos=240.0, 
        conceptos=[CFDIItem("Suscripción Software", 1, 1000.0), CFDIItem("Papelería Diversa", 1, 500.0)]
    )
    engine = DeductionEngine()
    results = engine.analyze_cfdi(mock_data)
    for res in results:
        print(f"Sugerencia: {res.concept} | Monto: {res.amount} | Razón: {res.reason}")
