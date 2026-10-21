"""
schemas.py
Defines the shape of a clean invoice using Pydantic.
The LLM will be asked to fill in this shape.
"""

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class LineItem(BaseModel):
    """One row in the invoice table."""

    description: str
    quantity: float
    unit_price: float
    line_total: float


class Invoice(BaseModel):
    """A whole invoice.

    Almost every field is Optional (it may be None).
    Why? Some invoices will have missing fields. If the AI is forced to
    fill every box, it may invent a value. With Optional, it can say
    "not found" (None), and our code can flag the invoice later.
    """

    invoice_number: Optional[str] = None
    vendor: Optional[str] = None
    trn: Optional[str] = None
    po_number: Optional[str] = None
    invoice_date: Optional[date] = None
    due_date: Optional[date] = None
    payment_terms: Optional[str] = None
    currency: Optional[str] = None
    line_items: list[LineItem] = Field(default_factory=list)
    subtotal: Optional[float] = None
    vat: Optional[float] = None
    total: Optional[float] = None