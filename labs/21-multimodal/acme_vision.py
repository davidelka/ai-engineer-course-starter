"""The three synthetic Acme images of lesson 21: what to extract from each, and how to score it.

Images live in data/images/ (made by make_images.py); the correct answers in data/gold.json.

- receipt.png       a customer-meal receipt from "Cafe Noir" (phone-photo proportions, 900x1800)
- whiteboard.jpg    a photo-like whiteboard sketch of the Company Brain architecture (2400x1600)
- error_dialog.png  a screenshot of an error dialog in Spendwise, Acme's expense app (1280x800)

KINDS says how each field is compared (llmkit.fields.compare_field / your mine.field_accuracy):
money = a number with 2 decimals, whatever the currency sign; date = ISO yyyy-mm-dd;
int = an integer; text = case and spacing do not matter; code = exact after trimming;
list = the same set of items (text rules per item).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

LAB = Path(__file__).resolve().parent
IMAGES = LAB / "data" / "images"
GOLD = LAB / "data" / "gold.json"


class Receipt(BaseModel):
    """An expense receipt."""
    merchant: str = Field(description="Business name as printed at the top")
    date: str = Field(description="Purchase date, ISO format yyyy-mm-dd")
    currency: str = Field(description="ISO 4217 code, e.g. ILS, EUR, USD")
    subtotal: float = Field(description="Sum of the item lines, before tip")
    tip: Optional[float] = Field(description="Tip / service amount, null if none")
    total: float = Field(description="Amount charged")
    vat: Optional[float] = Field(description="VAT amount printed on the receipt, null if not printed")
    alcohol_total: float = Field(description="Sum of the alcoholic item lines (wine, beer...), 0 if none")
    card_last4: Optional[str] = Field(description="Last 4 digits of the payment card, null if cash")
    item_lines: int = Field(description="Number of distinct item lines (not quantities)")
    guests: Optional[int] = Field(description="Number of guests / covers if printed")


class Whiteboard(BaseModel):
    """A photo of a whiteboard architecture sketch."""
    title: str = Field(description="The title written at the top of the board")
    components: list[str] = Field(description="Names written inside the boxes, as written")
    arrows: int = Field(description="Number of arrows between boxes")
    todo_note: Optional[str] = Field(description="Text of the sticky note, null if none")
    date: Optional[str] = Field(description="Date written on the board, ISO yyyy-mm-dd if a year is clear, else as written")


class ErrorDialog(BaseModel):
    """A screenshot of an application error dialog."""
    app_name: str = Field(description="Application name in the window title")
    error_code: str = Field(description="The error code, exactly as shown")
    message: str = Field(description="The main error message sentence")
    request_id: Optional[str] = Field(description="Request / correlation id if shown")
    buttons: list[str] = Field(description="Button labels, left to right")
    timestamp: Optional[str] = Field(description="Timestamp shown in the dialog, as written")


SCHEMAS = {"receipt": Receipt, "whiteboard": Whiteboard, "error_dialog": ErrorDialog}
FILES = {"receipt": "receipt.png", "whiteboard": "whiteboard.jpg", "error_dialog": "error_dialog.png"}

KINDS = {
    "receipt": {"merchant": "text", "date": "date", "currency": "code", "subtotal": "money", "tip": "money",
                "total": "money", "vat": "money", "alcohol_total": "money", "card_last4": "code",
                "item_lines": "int", "guests": "int"},
    "whiteboard": {"title": "text", "components": "list", "arrows": "int", "todo_note": "text", "date": "text"},
    "error_dialog": {"app_name": "text", "error_code": "code", "message": "text", "request_id": "code",
                     "buttons": "list", "timestamp": "text"},
}

PROMPTS = {
    "receipt": "This is a photo of a restaurant receipt submitted with an expense claim. Extract the fields.",
    "whiteboard": "This is a photo of a whiteboard from an architecture meeting. Extract the fields.",
    "error_dialog": "This is a screenshot a user attached to a support ticket. Extract the fields.",
}
SYSTEM = ("You extract data from images for Acme's back office. Copy text exactly as it appears. "
          "If a field is not visible or not legible, return null rather than guessing.")


def gold() -> dict:
    return json.loads(GOLD.read_text(encoding="utf-8"))
