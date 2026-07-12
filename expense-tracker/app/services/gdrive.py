import io
import json
import os
import re
from typing import Optional

from sqlalchemy.orm import Session

from ..models import AppSetting

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
_CRED_PATHS = ["/data/google_credentials.json", "./data/google_credentials.json"]


def _client_config() -> Optional[dict]:
    for path in _CRED_PATHS:
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    return None


def _load_creds(db: Session):
    """Load and optionally refresh stored OAuth credentials."""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
    except ImportError:
        return None

    row = db.get(AppSetting, "gdrive_token")
    if not row:
        return None

    cfg = _client_config()
    if not cfg:
        return None

    web = cfg.get("web") or cfg.get("installed", {})
    data = json.loads(row.value)

    creds = Credentials(
        token=data.get("token"),
        refresh_token=data.get("refresh_token"),
        token_uri=web.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=web["client_id"],
        client_secret=web["client_secret"],
        scopes=SCOPES,
    )

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_creds(db, creds)
        except Exception:
            return None

    return creds if creds.valid else None


def _save_creds(db: Session, creds) -> None:
    from datetime import datetime
    payload = json.dumps({
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
    })
    row = db.get(AppSetting, "gdrive_token")
    if row:
        row.value = payload
        row.updated_at = datetime.utcnow()
    else:
        db.add(AppSetting(key="gdrive_token", value=payload))
    db.commit()


def is_connected(db: Session) -> bool:
    creds = _load_creds(db)
    return creds is not None


def credentials_file_present() -> bool:
    return _client_config() is not None


def get_auth_url(redirect_uri: str) -> Optional[str]:
    try:
        from google_auth_oauthlib.flow import Flow
    except ImportError:
        return None

    cfg = _client_config()
    if not cfg:
        return None

    flow = Flow.from_client_config(cfg, scopes=SCOPES, redirect_uri=redirect_uri)
    url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return url


def exchange_code(db: Session, code: str, redirect_uri: str) -> bool:
    try:
        from google_auth_oauthlib.flow import Flow
    except ImportError:
        return False

    cfg = _client_config()
    if not cfg:
        return False

    flow = Flow.from_client_config(cfg, scopes=SCOPES, redirect_uri=redirect_uri)
    flow.fetch_token(code=code)
    _save_creds(db, flow.credentials)
    return True


def _get_or_create_folder(service, name: str, parent_id: Optional[str]) -> str:
    safe = name.replace("'", "\\'")
    q = f"name='{safe}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        q += f" and '{parent_id}' in parents"

    res = service.files().list(q=q, fields="files(id)", pageSize=1).execute()
    files = res.get("files", [])
    if files:
        return files[0]["id"]

    meta: dict = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        meta["parents"] = [parent_id]
    folder = service.files().create(body=meta, fields="id").execute()
    return folder["id"]


def upload_receipt(
    db: Session,
    content: bytes,
    filename: str,
    mime_type: str,
    category_name: str,
) -> Optional[str]:
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseUpload
    except ImportError:
        return None

    creds = _load_creds(db)
    if not creds:
        return None

    service = build("drive", "v3", credentials=creds)

    # Root "Expense Receipts" folder
    root_row = db.get(AppSetting, "gdrive_folder_id")
    if root_row:
        root_id = root_row.value
    else:
        root_id = _get_or_create_folder(service, "Expense Receipts", None)
        from datetime import datetime
        db.add(AppSetting(key="gdrive_folder_id", value=root_id))
        db.commit()

    # Per-category subfolder
    cat_id = _get_or_create_folder(service, category_name, root_id)

    # Upload
    media = MediaIoBaseUpload(io.BytesIO(content), mimetype=mime_type, resumable=False)
    uploaded = service.files().create(
        body={"name": filename, "parents": [cat_id]},
        media_body=media,
        fields="id,webViewLink",
    ).execute()

    # Make readable by anyone with the link
    service.permissions().create(
        fileId=uploaded["id"],
        body={"type": "anyone", "role": "reader"},
    ).execute()

    return uploaded.get("webViewLink")
