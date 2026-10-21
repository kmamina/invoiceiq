"""
checks.py
Deterministic checks on an extracted invoice.
Plain Python only. No AI is used here, so the same invoice
always gets the same result.
"""

from pydantic import BaseModel

from schemas import Invoice

VAT_RATE = 0.05      # UAE VAT is 5 percent
TOLERANCE = 0.01     # allow a difference of 1 fils (0.01 AED) for rounding

# Fields that every invoice must have
REQUIRED_FIELDS = [
    "invoice_number", "vendor", "trn", "po_number", "invoice_date",
    "due_date", "payment_terms", "currency", "subtotal", "vat", "total",
]


class CheckResult(BaseModel):
    """The result of ONE check."""

    name: str
    passed: bool
    message: str


def _pass(name, message):
    return CheckResult(name=name, passed=True, message=message)


def _fail(name, message):
    return CheckResult(name=name, passed=False, message=message)


def close(a, b):
    """True if two money amounts are equal, allowing for tiny rounding differences.
    (Computers store some decimals inexactly, so we never compare with ==.)"""
    return abs(a - b) <= TOLERANCE


# ---------- the 7 checks ----------

def check_required_fields(invoice: Invoice):
    missing = [field for field in REQUIRED_FIELDS if getattr(invoice, field) in (None, "")]
    if not invoice.line_items:
        missing.append("line_items")
    if missing:
        return _fail("required_fields", "Missing: " + ", ".join(missing))
    return _pass("required_fields", "All required fields are present")


def check_trn_format(invoice: Invoice):
    trn = invoice.trn
    if trn is None:
        return _fail("trn_format", "TRN is missing")
    if trn.isdigit() and len(trn) == 15:
        return _pass("trn_format", "TRN has 15 digits")
    return _fail("trn_format", f"TRN '{trn}' is not 15 digits")


def check_date_order(invoice: Invoice):
    if invoice.invoice_date is None or invoice.due_date is None:
        return _fail("date_order", "Cannot check: a date is missing")
    days = (invoice.due_date - invoice.invoice_date).days
    if days < 0:
        return _fail("date_order", f"Due date is {abs(days)} days BEFORE the invoice date")
    return _pass("date_order", f"Due date is {days} days after the invoice date")


def check_line_math(invoice: Invoice):
    if not invoice.line_items:
        return _fail("line_math", "Cannot check: there are no line items")
    problems = []
    for number, item in enumerate(invoice.line_items, start=1):
        expected = item.quantity * item.unit_price
        if not close(expected, item.line_total):
            problems.append(
                f"line {number}: {item.quantity:g} x {item.unit_price:,.2f} = {expected:,.2f}, "
                f"but invoice says {item.line_total:,.2f}"
            )
    if problems:
        return _fail("line_math", "; ".join(problems))
    return _pass("line_math", "Every line: quantity x unit price = line total")


def check_subtotal(invoice: Invoice):
    if not invoice.line_items or invoice.subtotal is None:
        return _fail("subtotal", "Cannot check: line items or subtotal missing")
    expected = sum(item.line_total for item in invoice.line_items)
    if close(expected, invoice.subtotal):
        return _pass("subtotal", f"Line totals add up to the subtotal ({expected:,.2f})")
    return _fail("subtotal", f"Line totals add up to {expected:,.2f}, but subtotal says {invoice.subtotal:,.2f}")


def check_vat(invoice: Invoice):
    if invoice.subtotal is None or invoice.vat is None:
        return _fail("vat", "Cannot check: subtotal or VAT missing")
    expected = invoice.subtotal * VAT_RATE
    if close(expected, invoice.vat):
        return _pass("vat", f"VAT is 5% of the subtotal ({expected:,.2f})")
    return _fail("vat", f"5% of {invoice.subtotal:,.2f} is {expected:,.2f}, but VAT says {invoice.vat:,.2f}")


def check_total(invoice: Invoice):
    if invoice.subtotal is None or invoice.vat is None or invoice.total is None:
        return _fail("total", "Cannot check: subtotal, VAT or total missing")
    expected = invoice.subtotal + invoice.vat
    if close(expected, invoice.total):
        return _pass("total", f"Subtotal + VAT = total ({expected:,.2f})")
    return _fail("total", f"Subtotal + VAT is {expected:,.2f}, but total says {invoice.total:,.2f}")


ALL_CHECKS = [
    check_required_fields,
    check_trn_format,
    check_date_order,
    check_line_math,
    check_subtotal,
    check_vat,
    check_total,
]


def run_all_checks(invoice: Invoice):
    """Run every check and return a list of CheckResult."""
    return [check(invoice) for check in ALL_CHECKS]