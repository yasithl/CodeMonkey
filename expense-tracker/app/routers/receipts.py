import mimetypes
import re
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Transaction
from ..services import gdrive

router = APIRouter(tags=["receipts"])

ALLOWED_MIME_PREFIXES = ("image/", "application/pdf")
MAX_BYTES = 20 * 1024 * 1024  # 20 MB


# ---- Google Drive OAuth flow ------------------------------------

@router.get("/api/gdrive/status")
def gdrive_status(db: Session = Depends(get_db)):
    return {
        "credentials_file_found": gdrive.credentials_file_present(),
        "connected": gdrive.is_connected(db),
    }


@router.get("/api/gdrive/auth")
def gdrive_auth(request: Request, db: Session = Depends(get_db)):
    redirect_uri = str(request.base_url).rstrip("/") + "/api/gdrive/callback"
    url = gdrive.get_auth_url(redirect_uri)
    if not url:
        raise HTTPException(
            400,
            "google_credentials.json not found in the data/ directory. "
            "See Settings → Google Drive for setup instructions.",
        )
    return RedirectResponse(url)


@router.get("/api/gdrive/callback")
def gdrive_callback(code: str, request: Request, db: Session = Depends(get_db)):
    redirect_uri = str(request.base_url).rstrip("/") + "/api/gdrive/callback"
    ok = gdrive.exchange_code(db, code, redirect_uri)
    if not ok:
        raise HTTPException(500, "Failed to exchange authorisation code for tokens.")
    return RedirectResponse("/#/settings?gdrive=connected")


# ---- Receipt upload / removal -----------------------------------

@router.post("/api/transactions/{tx_id}/receipt")
async def upload_receipt(
    tx_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    tx = db.get(Transaction, tx_id)
    if not tx:
        raise HTTPException(404, "Transaction not found")

    if not gdrive.is_connected(db):
        raise HTTPException(
            503,
            "Google Drive is not connected. Go to Settings → Google Drive to authorise.",
        )

    mime = file.content_type or mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream"
    if not any(mime.startswith(p) for p in ALLOWED_MIME_PREFIXES):
        raise HTTPException(415, "Only images and PDFs are accepted as receipts.")

    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(413, "File too large (max 20 MB).")

    fname = file.filename or "receipt"
    ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else "bin"
    safe_desc = re.sub(r"[^a-z0-9]+", "_", (tx.description or "receipt")[:40].lower()).strip("_")
    saved_name = f"{tx.date}_{safe_desc}_{tx.id}.{ext}"

    cat_name = tx.category.name if tx.category else "Uncategorised"

    link = gdrive.upload_receipt(db, content, saved_name, mime, cat_name)
    if not link:
        raise HTTPException(500, "Upload to Google Drive failed.")

    tx.receipt_url = link
    db.commit()

    return {"receipt_url": link}


@router.delete("/api/transactions/{tx_id}/receipt")
def remove_receipt(tx_id: int, db: Session = Depends(get_db)):
    tx = db.get(Transaction, tx_id)
    if not tx:
        raise HTTPException(404, "Transaction not found")
    tx.receipt_url = None
    db.commit()
    return {"ok": True}
