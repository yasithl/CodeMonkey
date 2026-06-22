import csv
import hashlib
import io
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional

import chardet
from dateutil import parser as dateparser


@dataclass
class ParsedRow:
    date: date
    description: str
    amount: Decimal
    merchant: Optional[str] = None
    account_ref: Optional[str] = None


@dataclass
class ColumnMap:
    date_col: str
    description_col: str
    amount_col: Optional[str] = None
    debit_col: Optional[str] = None
    credit_col: Optional[str] = None
    merchant_col: Optional[str] = None
    account_col: Optional[str] = None
    date_format: Optional[str] = None
    format_name: str = "generic"


# Fingerprints: set of lowercase header substrings that must all be present
FORMAT_FINGERPRINTS = [
    # Starling Bank
    {
        "name": "starling",
        "required": {"date", "counter party", "amount (gbp)"},
        "date_col": "Date",
        "desc_col": "Reference",
        "amount_col": "Amount (GBP)",
        "merchant_col": "Counter Party",
    },
    # Monzo
    {
        "name": "monzo",
        "required": {"transaction id", "date", "amount", "name"},
        "date_col": "Date",
        "desc_col": "Description",
        "amount_col": "Amount",
        "merchant_col": "Name",
    },
    # Barclays
    {
        "name": "barclays",
        "required": {"number", "date", "account", "amount", "payee"},
        "date_col": "Date",
        "desc_col": "Memo",
        "amount_col": "Amount",
        "merchant_col": "Payee",
        "account_col": "Account",
    },
    # Lloyds / TSB / Halifax
    {
        "name": "lloyds",
        "required": {"transaction date", "transaction type", "sort code", "account number"},
        "date_col": "Transaction Date",
        "desc_col": "Transaction Description",
        "debit_col": "Debit Amount",
        "credit_col": "Credit Amount",
    },
    # Nationwide
    {
        "name": "nationwide",
        "required": {"date", "transactions", "debits", "credits", "balance"},
        "date_col": "Date",
        "desc_col": "Transactions",
        "debit_col": "Debits",
        "credit_col": "Credits",
    },
    # HSBC
    {
        "name": "hsbc",
        "required": {"date", "description", "amount"},
        "date_col": "Date",
        "desc_col": "Description",
        "amount_col": "Amount",
    },
    # NatWest / RBS
    {
        "name": "natwest",
        "required": {"date", "type", "description", "value"},
        "date_col": "Date",
        "desc_col": "Description",
        "amount_col": "Value",
    },
    # Santander UK
    {
        "name": "santander",
        "required": {"date", "description", "amount", "balance"},
        "date_col": "Date",
        "desc_col": "Description",
        "amount_col": "Amount",
    },
    # Generic split debit/credit
    {
        "name": "generic_split",
        "required": {"date", "debit", "credit"},
        "date_col": "Date",
        "desc_col": None,  # resolved during detection
        "debit_col": "Debit",
        "credit_col": "Credit",
    },
]


def detect_encoding(raw_bytes: bytes) -> str:
    result = chardet.detect(raw_bytes[:10000])
    enc = result.get("encoding") or "utf-8"
    return enc if enc.lower() not in ("ascii",) else "utf-8"


def _resolve_col(headers: list[str], target: str) -> Optional[str]:
    """Case-insensitive column name resolution."""
    if target is None:
        return None
    for h in headers:
        if h.strip().lower() == target.strip().lower():
            return h
    # Partial match fallback
    for h in headers:
        if target.strip().lower() in h.strip().lower():
            return h
    return None


def detect_format(headers: list[str]) -> ColumnMap:
    headers_lower = {h.strip().lower() for h in headers}

    for fp in FORMAT_FINGERPRINTS:
        if fp["required"].issubset(headers_lower):
            desc_col = _resolve_col(headers, fp["desc_col"]) if fp.get("desc_col") else None
            if desc_col is None:
                # Pick the first non-date, non-amount column
                for h in headers:
                    hl = h.strip().lower()
                    if not any(x in hl for x in ["date", "debit", "credit", "amount", "balance", "id"]):
                        desc_col = h
                        break
            return ColumnMap(
                date_col=_resolve_col(headers, fp["date_col"]) or headers[0],
                description_col=desc_col or headers[1],
                amount_col=_resolve_col(headers, fp.get("amount_col")),
                debit_col=_resolve_col(headers, fp.get("debit_col")),
                credit_col=_resolve_col(headers, fp.get("credit_col")),
                merchant_col=_resolve_col(headers, fp.get("merchant_col")),
                account_col=_resolve_col(headers, fp.get("account_col")),
                format_name=fp["name"],
            )

    return _detect_generic(headers)


def _detect_generic(headers: list[str]) -> ColumnMap:
    date_col = desc_col = amount_col = debit_col = credit_col = None

    for h in headers:
        hl = h.strip().lower()
        if date_col is None and any(x in hl for x in ["date", "posted", "time", "when"]):
            date_col = h
        elif desc_col is None and any(x in hl for x in ["desc", "detail", "memo", "narr", "ref", "note", "payee", "merchant", "name", "transaction"]):
            desc_col = h
        elif amount_col is None and hl in {"amount", "value", "sum", "total", "gbp", "usd", "eur", "net"}:
            amount_col = h
        elif debit_col is None and any(x in hl for x in ["debit", "withdrawal", "out", "payment made"]):
            debit_col = h
        elif credit_col is None and any(x in hl for x in ["credit", "deposit", "in", "payment received"]):
            credit_col = h

    if desc_col is None:
        for h in headers:
            if h not in {date_col, amount_col, debit_col, credit_col}:
                desc_col = h
                break

    return ColumnMap(
        date_col=date_col or headers[0],
        description_col=desc_col or (headers[1] if len(headers) > 1 else headers[0]),
        amount_col=amount_col,
        debit_col=debit_col,
        credit_col=credit_col,
        format_name="generic",
    )


def _get(row: dict, col: Optional[str]) -> str:
    if col is None:
        return ""
    # Exact key first
    if col in row:
        return (row[col] or "").strip()
    # Case-insensitive
    for k, v in row.items():
        if k.strip().lower() == col.strip().lower():
            return (v or "").strip()
    return ""


def _parse_amount(val: str) -> Optional[Decimal]:
    if not val:
        return None
    cleaned = re.sub(r"[£$€,\s]", "", val).strip()
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _parse_date(val: str) -> Optional[date]:
    if not val:
        return None
    try:
        return dateparser.parse(val.strip(), dayfirst=True).date()
    except Exception:
        return None


def compute_hash(tx_date: date, description: str, amount: Decimal) -> str:
    key = f"{tx_date.isoformat()}|{description.strip().lower()}|{amount}"
    return hashlib.sha256(key.encode()).hexdigest()


def parse_csv(content: bytes) -> tuple[str, list[ParsedRow], int]:
    """Parse CSV bytes. Returns (format_name, rows, skipped_count)."""
    encoding = detect_encoding(content)
    text = content.decode(encoding, errors="replace").lstrip("﻿")

    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    headers = list(reader.fieldnames or [])
    if not headers:
        return "unknown", [], 0

    col_map = detect_format(headers)
    rows: list[ParsedRow] = []
    skipped = 0

    for raw in reader:
        date_str = _get(raw, col_map.date_col)
        desc_str = _get(raw, col_map.description_col)
        merchant_str = _get(raw, col_map.merchant_col)
        account_str = _get(raw, col_map.account_col)

        tx_date = _parse_date(date_str)
        if tx_date is None:
            skipped += 1
            continue

        amount: Optional[Decimal] = None
        if col_map.amount_col:
            amount = _parse_amount(_get(raw, col_map.amount_col))
        if amount is None and col_map.debit_col and col_map.credit_col:
            debit = _parse_amount(_get(raw, col_map.debit_col))
            credit = _parse_amount(_get(raw, col_map.credit_col))
            if debit and debit != Decimal("0"):
                amount = -abs(debit)
            elif credit and credit != Decimal("0"):
                amount = abs(credit)

        if amount is None or amount == Decimal("0"):
            skipped += 1
            continue

        if not desc_str and merchant_str:
            desc_str = merchant_str
        elif not desc_str:
            desc_str = "Unknown Transaction"

        rows.append(ParsedRow(
            date=tx_date,
            description=desc_str,
            amount=amount,
            merchant=merchant_str or None,
            account_ref=account_str or None,
        ))

    return col_map.format_name, rows, skipped
