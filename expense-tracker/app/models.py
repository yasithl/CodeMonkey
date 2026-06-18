from datetime import datetime, date as DateType
from decimal import Decimal
from typing import Optional, List
from sqlalchemy import (
    String, Integer, Float, Boolean, DateTime, Date,
    Numeric, ForeignKey, Text, Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    gst_claimable: Mapped[bool] = mapped_column(Boolean, default=True)
    color: Mapped[str] = mapped_column(String(7), default="#6c757d")
    is_income: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    rules: Mapped[List["CategoryRule"]] = relationship(
        "CategoryRule", back_populates="category", cascade="all, delete-orphan"
    )
    transactions: Mapped[List["Transaction"]] = relationship(
        "Transaction", back_populates="category"
    )


class CategoryRule(Base):
    __tablename__ = "category_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE")
    )
    keyword: Mapped[str] = mapped_column(String(200))
    match_type: Mapped[str] = mapped_column(String(20), default="contains")
    field: Mapped[str] = mapped_column(String(20), default="description")
    priority: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(20), default="manual")
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    category: Mapped["Category"] = relationship("Category", back_populates="rules")


class StatementUpload(Base):
    __tablename__ = "statement_uploads"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    original_filename: Mapped[str] = mapped_column(String(255))
    bank_format: Mapped[str] = mapped_column(String(50), default="generic")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    imported_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="processed")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    transactions: Mapped[List["Transaction"]] = relationship(
        "Transaction", back_populates="upload"
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    upload_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("statement_uploads.id", ondelete="SET NULL"), nullable=True
    )
    date: Mapped[DateType] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String(500))
    merchant: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="GBP")
    account_ref: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    category_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    category_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    reconciliation_status: Mapped[str] = mapped_column(String(20), default="pending")
    gst_amount: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=0)
    gst_claimable: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tx_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    upload: Mapped[Optional["StatementUpload"]] = relationship(
        "StatementUpload", back_populates="transactions"
    )
    category: Mapped[Optional["Category"]] = relationship(
        "Category", back_populates="transactions"
    )

    __table_args__ = (
        Index("ix_transactions_date", "date"),
        Index("ix_transactions_status", "reconciliation_status"),
        Index("ix_transactions_category", "category_id"),
    )


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
