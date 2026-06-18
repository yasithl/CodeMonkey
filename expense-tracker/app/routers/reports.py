from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from ..database import get_db
from ..services.report_builder import build_report, export_csv

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _resolve_dates(preset: str, from_date, to_date) -> tuple[date, date]:
    today = date.today()
    if preset == "2m":
        end = today.replace(day=1) - timedelta(days=1)
        start = (end.replace(day=1) - timedelta(days=1)).replace(day=1)
        return start, end
    if preset == "6m":
        end = today.replace(day=1) - timedelta(days=1)
        start_month = end.month - 5
        start_year = end.year
        if start_month <= 0:
            start_month += 12
            start_year -= 1
        return date(start_year, start_month, 1), end
    if preset == "ytd":
        return date(today.year, 1, 1), today
    if preset == "this_month":
        return today.replace(day=1), today
    if preset == "last_month":
        end = today.replace(day=1) - timedelta(days=1)
        return end.replace(day=1), end
    # Custom
    if not from_date or not to_date:
        raise HTTPException(400, "Provide from_date and to_date or a preset")
    if from_date > to_date:
        raise HTTPException(400, "from_date must be before to_date")
    return from_date, to_date


@router.get("/summary")
def report_summary(
    preset: str = Query("6m"),
    from_date: date = None,
    to_date: date = None,
    db: Session = Depends(get_db),
):
    start, end = _resolve_dates(preset, from_date, to_date)
    return build_report(db, start, end)


@router.get("/export")
def export_transactions(
    preset: str = Query("6m"),
    from_date: date = None,
    to_date: date = None,
    db: Session = Depends(get_db),
):
    start, end = _resolve_dates(preset, from_date, to_date)
    csv_data = export_csv(db, start, end)
    filename = f"expenses_{start}_{end}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
