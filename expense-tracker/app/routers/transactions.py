from datetime import date
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from ..database import get_db
from ..models import Transaction, Category
from ..schemas import TransactionOut, TransactionUpdate
from ..services.categorizer import learn_from_manual, rerun_all_pending
from ..routers.settings import get_gst_rate

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


def _to_out(tx: Transaction) -> dict:
    return {
        "id": tx.id,
        "date": tx.date,
        "description": tx.description,
        "merchant": tx.merchant,
        "amount": tx.amount,
        "currency": tx.currency,
        "category_id": tx.category_id,
        "category_name": tx.category.name if tx.category else None,
        "category_confidence": tx.category_confidence,
        "reconciliation_status": tx.reconciliation_status,
        "gst_amount": tx.gst_amount,
        "gst_claimable": tx.gst_claimable,
        "notes": tx.notes,
        "receipt_url": tx.receipt_url,
        "upload_id": tx.upload_id,
        "created_at": tx.created_at,
    }


@router.get("")
def list_transactions(
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    category_id: Optional[int] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(Transaction)
    if from_date:
        q = q.filter(Transaction.date >= from_date)
    if to_date:
        q = q.filter(Transaction.date <= to_date)
    if category_id is not None:
        q = q.filter(Transaction.category_id == category_id)
    if status:
        q = q.filter(Transaction.reconciliation_status == status)
    if search:
        term = f"%{search.lower()}%"
        q = q.filter(
            or_(
                Transaction.description.ilike(term),
                Transaction.merchant.ilike(term),
                Transaction.notes.ilike(term),
            )
        )

    total = q.count()
    txns = (
        q.order_by(Transaction.date.desc(), Transaction.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_to_out(t) for t in txns],
    }


@router.get("/pending")
def list_pending(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(Transaction).filter(Transaction.reconciliation_status == "pending")
    total = q.count()
    txns = (
        q.order_by(Transaction.date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_to_out(t) for t in txns],
    }


@router.get("/summary")
def get_summary(db: Session = Depends(get_db)):
    from sqlalchemy import func
    total = db.query(func.count(Transaction.id)).scalar()
    pending = db.query(func.count(Transaction.id)).filter_by(reconciliation_status="pending").scalar()
    expense_sum = (
        db.query(func.sum(Transaction.amount))
        .filter(Transaction.amount < 0)
        .scalar()
    ) or Decimal("0")
    gst_sum = (
        db.query(func.sum(Transaction.gst_amount))
        .filter(Transaction.gst_claimable == True)
        .scalar()
    ) or Decimal("0")
    return {
        "total_transactions": total,
        "pending_reconciliation": pending,
        "total_expenses": float(abs(expense_sum)),
        "total_gst_claimable": float(gst_sum),
    }


@router.get("/{tx_id}")
def get_transaction(tx_id: int, db: Session = Depends(get_db)):
    tx = db.get(Transaction, tx_id)
    if not tx:
        raise HTTPException(404, "Transaction not found")
    return _to_out(tx)


@router.patch("/{tx_id}")
def update_transaction(tx_id: int, body: TransactionUpdate, db: Session = Depends(get_db)):
    tx = db.get(Transaction, tx_id)
    if not tx:
        raise HTTPException(404, "Transaction not found")

    gst_rate = get_gst_rate(db)

    if body.category_id is not None:
        learn_from_manual(tx, body.category_id, db, gst_rate)
    if body.reconciliation_status is not None:
        tx.reconciliation_status = body.reconciliation_status
    if body.gst_claimable is not None:
        tx.gst_claimable = body.gst_claimable
        if body.gst_claimable and tx.amount < 0:
            rate = Decimal(str(gst_rate))
            tx.gst_amount = (abs(tx.amount) * rate / (1 + rate)).quantize(Decimal("0.0001"))
        else:
            tx.gst_amount = Decimal("0")
    if body.notes is not None:
        tx.notes = body.notes

    db.commit()
    db.refresh(tx)
    return _to_out(tx)


@router.post("/bulk-categorize")
def bulk_categorize(db: Session = Depends(get_db)):
    gst_rate = get_gst_rate(db)
    updated = rerun_all_pending(db, gst_rate)
    return {"updated": updated}
