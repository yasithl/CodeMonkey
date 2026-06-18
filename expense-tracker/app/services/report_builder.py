import csv
import io
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session
from ..models import Transaction


def build_report(db: Session, from_date: date, to_date: date) -> dict:
    txns = (
        db.query(Transaction)
        .filter(Transaction.date >= from_date, Transaction.date <= to_date)
        .all()
    )

    total_expenses = Decimal("0")
    total_income = Decimal("0")
    total_gst_paid = Decimal("0")
    total_gst_claimable = Decimal("0")
    pending_count = 0
    by_category: dict[str, dict] = {}
    monthly: dict[str, dict] = {}

    for tx in txns:
        if tx.reconciliation_status == "pending":
            pending_count += 1

        if tx.amount < 0:
            total_expenses += abs(tx.amount)
            total_gst_paid += abs(tx.gst_amount)
            if tx.gst_claimable:
                total_gst_claimable += abs(tx.gst_amount)
        else:
            total_income += tx.amount

        cat_name = tx.category.name if tx.category else "Uncategorised"
        cat_color = tx.category.color if tx.category else "#adb5bd"
        is_income = tx.category.is_income if tx.category else False

        if cat_name not in by_category:
            by_category[cat_name] = {
                "category": cat_name,
                "color": cat_color,
                "is_income": is_income,
                "total": Decimal("0"),
                "gst_claimable": Decimal("0"),
                "count": 0,
            }
        by_category[cat_name]["total"] += abs(tx.amount)
        if tx.gst_claimable:
            by_category[cat_name]["gst_claimable"] += abs(tx.gst_amount)
        by_category[cat_name]["count"] += 1

        month_key = tx.date.strftime("%Y-%m")
        if month_key not in monthly:
            monthly[month_key] = {
                "month": month_key,
                "expenses": Decimal("0"),
                "income": Decimal("0"),
                "gst_claimable": Decimal("0"),
                "transaction_count": 0,
            }
        if tx.amount < 0:
            monthly[month_key]["expenses"] += abs(tx.amount)
            if tx.gst_claimable:
                monthly[month_key]["gst_claimable"] += abs(tx.gst_amount)
        else:
            monthly[month_key]["income"] += tx.amount
        monthly[month_key]["transaction_count"] += 1

    def _f(d: Decimal) -> float:
        return float(d.quantize(Decimal("0.01")))

    return {
        "from_date": from_date,
        "to_date": to_date,
        "total_expenses": _f(total_expenses),
        "total_income": _f(total_income),
        "total_gst_paid": _f(total_gst_paid),
        "total_gst_claimable": _f(total_gst_claimable),
        "net_vat_position": _f(total_gst_claimable),
        "transaction_count": len(txns),
        "pending_count": pending_count,
        "by_category": sorted(
            [
                {
                    **{k: v for k, v in c.items() if k not in ("total", "gst_claimable")},
                    "total": _f(c["total"]),
                    "gst_claimable": _f(c["gst_claimable"]),
                }
                for c in by_category.values()
            ],
            key=lambda x: x["total"],
            reverse=True,
        ),
        "monthly_breakdown": sorted(
            [
                {
                    "month": m["month"],
                    "expenses": _f(m["expenses"]),
                    "income": _f(m["income"]),
                    "gst_claimable": _f(m["gst_claimable"]),
                    "transaction_count": m["transaction_count"],
                }
                for m in monthly.values()
            ],
            key=lambda x: x["month"],
        ),
    }


def export_csv(db: Session, from_date: date, to_date: date) -> str:
    txns = (
        db.query(Transaction)
        .filter(Transaction.date >= from_date, Transaction.date <= to_date)
        .order_by(Transaction.date)
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Date", "Description", "Merchant", "Amount", "Currency",
        "Category", "GST Amount", "GST Claimable", "Status", "Notes",
    ])

    for tx in txns:
        writer.writerow([
            tx.date.isoformat(),
            tx.description,
            tx.merchant or "",
            str(tx.amount),
            tx.currency,
            tx.category.name if tx.category else "",
            str(tx.gst_amount),
            "Yes" if tx.gst_claimable else "No",
            tx.reconciliation_status,
            tx.notes or "",
        ])

    return output.getvalue()
