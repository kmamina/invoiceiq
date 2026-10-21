"""
config.py
Business rules in ONE place, so they are easy to find and change.
"""

VAT_RATE = 0.05            # UAE VAT is 5 percent
TOLERANCE = 0.01           # allowed rounding difference: 1 fils (0.01 AED)

# Invoices with a total ABOVE this amount (AED, including VAT) need senior approval,
# so they can never be approved automatically.
APPROVAL_LIMIT = 50_000.00

# Payment terms (in days) agreed in each vendor's contract.
# The list follows the order of the vendor master (the 8 vendors).
VENDOR_TERMS_DAYS = [30, 30, 45, 60, 30, 45, 30, 60]