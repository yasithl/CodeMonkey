from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import AppSetting
from ..schemas import SettingOut, SettingUpdate
from ..config import settings as app_config

router = APIRouter(prefix="/api/settings", tags=["settings"])

DEFAULTS = {
    "gst_rate": str(app_config.GST_RATE),
    "default_currency": app_config.DEFAULT_CURRENCY,
    "company_name": "",
    "tax_period_start": "04",  # April (NZ tax year: 1 Apr – 31 Mar)
}


def get_setting(db: Session, key: str) -> str:
    row = db.get(AppSetting, key)
    if row:
        return row.value
    return DEFAULTS.get(key, "")


def get_gst_rate(db: Session) -> float:
    val = get_setting(db, "gst_rate")
    try:
        return float(val)
    except (ValueError, TypeError):
        return app_config.GST_RATE


@router.get("", response_model=list[SettingOut])
def list_settings(db: Session = Depends(get_db)):
    rows = db.query(AppSetting).all()
    existing = {r.key: r.value for r in rows}
    result = []
    for key, default in DEFAULTS.items():
        result.append(SettingOut(key=key, value=existing.get(key, default)))
    return result


@router.get("/{key}", response_model=SettingOut)
def get_one(key: str, db: Session = Depends(get_db)):
    return SettingOut(key=key, value=get_setting(db, key))


@router.put("/{key}", response_model=SettingOut)
def update_setting(key: str, body: SettingUpdate, db: Session = Depends(get_db)):
    from datetime import datetime
    row = db.get(AppSetting, key)
    if row:
        row.value = body.value
        row.updated_at = datetime.utcnow()
    else:
        db.add(AppSetting(key=key, value=body.value))
    db.commit()
    return SettingOut(key=key, value=body.value)
