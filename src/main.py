import sys
import argparse
from cfdi_parser import parse_cfdi
from deduction_engine import DeductionEngine
from compliance_alerts import ComplianceAlerts
from vault import Vault

def main():
    parser = argparse.ArgumentParser(description="FiscoMind CLI - Fiscal Intelligence for Mexico")
    parser.add_argument("command", choices=["parse", "deduce", "alerts", "vault"], help="Action to perform")
    parser.add_argument("--file", help="Path to XML file for parsing")
    parser.add_argument("--amount", type=float, help="Amount for deduction check")
    parser.add_argument("--category", help="Category for deduction check")
    parser.add_argument("--secret", help="Secret to store in vault")
    
    args = parser.parse_args()

    if args.command == "parse":
        if not args.file:
            print("Error: --file is required for parse")
            return
        with open(args.file, 'r') as f:
            xml_content = f.read()
        data = parse_cfdi(xml_content)
        print(f"--- CFDI Analysis ---\nRFC Emisor: {data.rfc_emisor}\nTotal: {data.total} {data.moneda}\nItems: {len(data.items)}")

    elif args.command == "deduce":
        if not args.amount or not args.category:
            print("Error: --amount and --category are required for deduce")
            return
        engine = DeductionEngine()
        res = engine.evaluate("Expense", args.amount, args.category)
        print(f"Deductible: {res.is_deductible}\nAmount: {res.amount}\nReason: {res.reason}")

    elif args.command == "alerts":
        cal = ComplianceAlerts()
        from datetime import date
        alerts = cal.get_upcoming_alerts(date.today())
        for a in alerts:
            print(f"📅 {a['date']} - {a['obligation']}: {a['description']}")

    elif args.command == "vault":
        vault = Vault()
        if args.secret:
            enc = vault.encrypt(args.secret)
            print(f"Secret stored as encrypted token: {enc.decode()}")
        else:
            print("Vault active. Use --secret to encrypt data.")

if __name__ == "__main__":
    main()
