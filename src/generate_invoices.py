"""
generate_invoices.py
Creates fake (synthetic) supplier invoices as PDF files,
and saves the correct answers as JSON files for testing later.
"""

import json
import random
from datetime import date, timedelta
from pathlib import Path

from faker import Faker
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

# Fixed seeds: you get the same fake data every time you run this.
Faker.seed(42)
random.seed(42)
fake = Faker()

# Folders (relative to the project folder)
BASE_DIR = Path(__file__).resolve().parent.parent
INVOICE_DIR = BASE_DIR / "data" / "invoices"
TRUTH_DIR = BASE_DIR / "data" / "ground_truth"
INVOICE_DIR.mkdir(parents=True, exist_ok=True)
TRUTH_DIR.mkdir(parents=True, exist_ok=True)

# The company that RECEIVES the invoices (our fake UAE company)
BUYER_NAME = "Desert Palm Trading LLC"
BUYER_TRN = "100998877600003"

VAT_RATE = 0.05  # UAE VAT is 5 percent


def make_vendors(count):
    """Make a list of fake vendors (suppliers)."""
    vendors = []
    for _ in range(count):
        vendors.append(
            {
                "name": fake.last_name() + " " + fake.company_suffix() + " LLC",
                "trn": "100" + "".join(str(random.randint(0, 9)) for _ in range(12)),
                "address": f"Office {random.randint(100, 999)}, "
                f"{fake.last_name()} Tower, Business Bay, Dubai, UAE",
            }
        )
    return vendors


VENDORS = make_vendors(8)

# Things a supplier might sell: (description, unit price in AED)
CATALOG = [
    ("A4 Copy Paper (box of 5 reams)", 85.00),
    ("Laser Printer Toner Cartridge", 320.00),
    ("Office Chair (ergonomic)", 750.00),
    ("Cleaning Service (monthly)", 1800.00),
    ("Laptop Docking Station", 450.00),
    ("Network Cable Cat6 (100 m)", 210.00),
    ("Whiteboard Markers (pack of 12)", 38.00),
    ("Annual Software Support", 5200.00),
    ("Courier Service (per shipment)", 65.00),
    ("Printing Services (per 1000 pages)", 140.00),
]


def make_invoice_data(number):
    """Make ONE correct (clean) invoice as a Python dictionary."""
    vendor = random.choice(VENDORS)
    invoice_date = date(2026, 1, 1) + timedelta(days=random.randint(0, 260))
    due_date = invoice_date + timedelta(days=30)

    line_items = []
    for description, unit_price in random.sample(CATALOG, random.randint(2, 5)):
        quantity = random.randint(1, 10)
        line_items.append(
            {
                "description": description,
                "quantity": quantity,
                "unit_price": unit_price,
                "line_total": round(quantity * unit_price, 2),
            }
        )

    subtotal = round(sum(item["line_total"] for item in line_items), 2)
    vat = round(subtotal * VAT_RATE, 2)
    total = round(subtotal + vat, 2)

    return {
        "invoice_number": f"INV-2026-{number:04d}",
        "vendor": vendor["name"],
        "vendor_address": vendor["address"],
        "trn": vendor["trn"],
        "po_number": f"PO-{random.randint(1000, 1999)}",
        "invoice_date": invoice_date.isoformat(),
        "due_date": due_date.isoformat(),
        "payment_terms": "Net 30 days",
        "currency": "AED",
        "line_items": line_items,
        "subtotal": subtotal,
        "vat": vat,
        "total": total,
    }


def draw_invoice(data, path):
    """Draw the invoice dictionary onto a PDF page."""
    c = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4
    left = 20 * mm
    right = width - 20 * mm
    y = height - 25 * mm  # start near the top of the page

    # Title
    c.setFont("Helvetica-Bold", 20)
    c.drawString(left, y, "TAX INVOICE")
    y -= 12 * mm

    # Vendor block
    c.setFont("Helvetica-Bold", 12)
    c.drawString(left, y, data["vendor"])
    y -= 6 * mm
    c.setFont("Helvetica", 10)
    c.drawString(left, y, data["vendor_address"])
    y -= 5 * mm
    c.drawString(left, y, f"TRN: {data['trn']}")
    y -= 12 * mm

    # Invoice details
    c.drawString(left, y, f"Invoice Number: {data['invoice_number']}")
    y -= 5 * mm
    c.drawString(left, y, f"Invoice Date: {data['invoice_date']}")
    y -= 5 * mm
    c.drawString(left, y, f"Due Date: {data['due_date']}")
    y -= 5 * mm
    c.drawString(left, y, f"PO Number: {data['po_number']}")
    y -= 12 * mm

    # Bill to
    c.setFont("Helvetica-Bold", 10)
    c.drawString(left, y, "Bill To:")
    y -= 5 * mm
    c.setFont("Helvetica", 10)
    c.drawString(left, y, BUYER_NAME)
    y -= 5 * mm
    c.drawString(left, y, f"TRN: {BUYER_TRN}")
    y -= 14 * mm

    # Table header
    c.setFont("Helvetica-Bold", 10)
    c.drawString(left, y, "Description")
    c.drawRightString(left + 115 * mm, y, "Qty")
    c.drawRightString(left + 145 * mm, y, "Unit Price")
    c.drawRightString(right, y, "Amount")
    y -= 3 * mm
    c.line(left, y, right, y)
    y -= 6 * mm

    # Table rows
    c.setFont("Helvetica", 10)
    for item in data["line_items"]:
        c.drawString(left, y, item["description"])
        c.drawRightString(left + 115 * mm, y, str(item["quantity"]))
        c.drawRightString(left + 145 * mm, y, f"{item['unit_price']:,.2f}")
        c.drawRightString(right, y, f"{item['line_total']:,.2f}")
        y -= 6 * mm

    c.line(left, y, right, y)
    y -= 8 * mm

    # Totals
    c.drawRightString(left + 145 * mm, y, "Subtotal:")
    c.drawRightString(right, y, f"{data['subtotal']:,.2f}")
    y -= 6 * mm
    c.drawRightString(left + 145 * mm, y, "VAT (5%):")
    c.drawRightString(right, y, f"{data['vat']:,.2f}")
    y -= 6 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(left + 145 * mm, y, f"Total ({data['currency']}):")
    c.drawRightString(right, y, f"{data['total']:,.2f}")
    y -= 14 * mm

    # Payment terms
    c.setFont("Helvetica", 10)
    c.drawString(left, y, f"Payment Terms: {data['payment_terms']}")

    c.save()


if __name__ == "__main__":
    for n in range(1, 6):
        data = make_invoice_data(n)

        pdf_path = INVOICE_DIR / f"{data['invoice_number']}.pdf"
        draw_invoice(data, pdf_path)

        truth_path = TRUTH_DIR / f"{data['invoice_number']}.json"
        truth_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        print(f"Created {pdf_path.name}  |  {data['vendor']}  |  total {data['total']:,.2f} AED")