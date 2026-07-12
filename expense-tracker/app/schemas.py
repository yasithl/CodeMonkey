from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Any
from pydantic import BaseModel, ConfigDict


class CategoryRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    category_id: int
    keyword: str
    match_type: str
    field: str
    priority: int
    source: str
    confidence: float
    hit_count: int
    created_at: datetime


class CategoryRuleCreate(BaseModel):
    keyword: str
    match_type: str = "contains"
    field: str = "description"
    priority: int = 0


class CategoryBase(BaseModel):
    name: str
    description: Optional[str] = None
    gst_claimable: bool = True
    color: str = "#6c757d"
    is_income: bool = False


class CategoryCreate(CategoryBase):
    pass


class CategoryOut(CategoryBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    rules: List[CategoryRuleOut] = []


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    date: date
    description: str
    merchant: Optional[str]
    amount: Decimal
    currency: str
    category_id: Optional[int]
    category_name: Optional[str] = None
    category_confidence: float
    reconciliation_status: str
    gst_amount: Decimal
    gst_claimable: bool
    notes: Optional[str]
    receipt_url: Optional[str]
    upload_id: Optional[int]
    created_at: datetime


class TransactionUpdate(BaseModel):
    category_id: Optional[int] = None
    reconciliation_status: Optional[str] = None
    gst_claimable: Optional[bool] = None
    notes: Optional[str] = None
    receipt_url: Optional[str] = None


class UploadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    original_filename: str
    bank_format: str
    uploaded_at: datetime
    row_count: int
    imported_count: int
    duplicate_count: int
    status: str
    error_message: Optional[str]


class SettingOut(BaseModel):
    key: str
    value: str


class SettingUpdate(BaseModel):
    value: str


class ReportOut(BaseModel):
    from_date: date
    to_date: date
    total_expenses: float
    total_income: float
    total_gst_paid: float
    total_gst_claimable: float
    net_vat_position: float
    transaction_count: int
    pending_count: int
    by_category: List[Any]
    monthly_breakdown: List[Any]
