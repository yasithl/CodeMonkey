import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Transaction, Receipt
from ..schemas import ReceiptOut
from ..config import settings as app_config

router = APIRouter(tags=["receipts"])

ALLOWED_EXTENSIONS = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".heic": "image/heic",
    ".pdf": "application/pdf",
}
MAX_SIZE = 10 * 1024 * 1024


@router.post("/api/transactions/{tx_id}/receipts", response_model=ReceiptOut, status_code=201)
async def upload_receipt(tx_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    tx = db.get(Transaction, tx_id)
    if not tx:
        raise HTTPException(404, "Transaction not found")

    fname = file.filename or "receipt"
    ext = os.path.splitext(fname)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, "Unsupported file type. Use JPG, PNG, WEBP, GIF, HEIC or PDF")

    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(413, "File too large (max 10 MB)")

    os.makedirs(app_config.RECEIPTS_DIR, exist_ok=True)
    saved_name = f"{uuid.uuid4().hex}{ext}"
    with open(os.path.join(app_config.RECEIPTS_DIR, saved_name), "wb") as fh:
        fh.write(content)

    receipt = Receipt(
        transaction_id=tx.id,
        filename=saved_name,
        original_filename=fname,
        content_type=ALLOWED_EXTENSIONS[ext],
        size=len(content),
    )
    db.add(receipt)
    db.commit()
    db.refresh(receipt)
    return receipt


@router.get("/api/transactions/{tx_id}/receipts", response_model=list[ReceiptOut])
def list_receipts(tx_id: int, db: Session = Depends(get_db)):
    tx = db.get(Transaction, tx_id)
    if not tx:
        raise HTTPException(404, "Transaction not found")
    return (
        db.query(Receipt)
        .filter(Receipt.transaction_id == tx_id)
        .order_by(Receipt.created_at.desc())
        .all()
    )


@router.get("/api/receipts/{receipt_id}/file")
def get_receipt_file(receipt_id: int, db: Session = Depends(get_db)):
    receipt = db.get(Receipt, receipt_id)
    if not receipt:
        raise HTTPException(404, "Receipt not found")
    path = os.path.join(app_config.RECEIPTS_DIR, receipt.filename)
    if not os.path.exists(path):
        raise HTTPException(404, "Receipt file missing on disk")
    return FileResponse(path, media_type=receipt.content_type, filename=receipt.original_filename)


@router.delete("/api/receipts/{receipt_id}")
def delete_receipt(receipt_id: int, db: Session = Depends(get_db)):
    receipt = db.get(Receipt, receipt_id)
    if not receipt:
        raise HTTPException(404, "Receipt not found")
    path = os.path.join(app_config.RECEIPTS_DIR, receipt.filename)
    if os.path.exists(path):
        os.remove(path)
    db.delete(receipt)
    db.commit()
    return {"ok": True}
