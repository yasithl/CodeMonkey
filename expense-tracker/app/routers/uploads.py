import os
import uuid
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import StatementUpload, Transaction
from ..schemas import UploadOut
from ..services.csv_parser import parse_csv, compute_hash
from ..services.categorizer import categorize, apply_category, CONFIDENCE_THRESHOLD
from ..routers.settings import get_gst_rate
from ..config import settings as app_config

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


@router.post("", response_model=UploadOut, status_code=201)
async def upload_statement(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    fname = file.filename or "upload.csv"
    if not fname.lower().endswith(".csv"):
        raise HTTPException(400, "Only CSV files are accepted")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 10 MB)")

    try:
        format_name, rows, skipped = parse_csv(content)
    except Exception as exc:
        raise HTTPException(400, f"Failed to parse CSV: {exc}") from exc

    os.makedirs(app_config.UPLOAD_DIR, exist_ok=True)
    saved_name = f"{uuid.uuid4().hex}_{fname}"
    with open(os.path.join(app_config.UPLOAD_DIR, saved_name), "wb") as fh:
        fh.write(content)

    upload = StatementUpload(
        filename=saved_name,
        original_filename=fname,
        bank_format=format_name,
        row_count=len(rows) + skipped,
    )
    db.add(upload)
    db.flush()

    existing_hashes: set[str] = {
        h[0] for h in db.query(Transaction.tx_hash).all()
    }
    gst_rate = get_gst_rate(db)
    imported = duplicates = 0

    for row in rows:
        tx_hash = compute_hash(row.date, row.description, row.amount)
        if tx_hash in existing_hashes:
            duplicates += 1
            continue

        cat_id, conf, _ = categorize(row.description, db)

        tx = Transaction(
            upload_id=upload.id,
            date=row.date,
            description=row.description,
            merchant=row.merchant,
            amount=row.amount,
            account_ref=row.account_ref,
            currency=app_config.DEFAULT_CURRENCY,
            category_confidence=conf,
            tx_hash=tx_hash,
        )

        if cat_id and conf >= CONFIDENCE_THRESHOLD:
            apply_category(tx, cat_id, "auto", db, gst_rate)
        else:
            tx.reconciliation_status = "pending"

        db.add(tx)
        existing_hashes.add(tx_hash)
        imported += 1

    upload.imported_count = imported
    upload.duplicate_count = duplicates
    db.commit()
    db.refresh(upload)
    return upload


@router.get("", response_model=list[UploadOut])
def list_uploads(db: Session = Depends(get_db)):
    return (
        db.query(StatementUpload)
        .order_by(StatementUpload.uploaded_at.desc())
        .all()
    )


@router.get("/{upload_id}", response_model=UploadOut)
def get_upload(upload_id: int, db: Session = Depends(get_db)):
    upload = db.get(StatementUpload, upload_id)
    if not upload:
        raise HTTPException(404, "Upload not found")
    return upload


@router.delete("/{upload_id}")
def delete_upload(upload_id: int, db: Session = Depends(get_db)):
    upload = db.get(StatementUpload, upload_id)
    if not upload:
        raise HTTPException(404, "Upload not found")
    db.delete(upload)
    db.commit()
    return {"ok": True}
