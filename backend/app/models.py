from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

Money = Numeric(14, 2)
TS = DateTime(timezone=True)


class Base(DeclarativeBase):
    pass


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    name_key: Mapped[str] = mapped_column(String(120), unique=True)
    created_at: Mapped[datetime] = mapped_column(TS)


class RFQ(Base):
    __tablename__ = "rfqs"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference_id: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(200))

    bid_start: Mapped[datetime] = mapped_column(TS)
    bid_close: Mapped[datetime] = mapped_column(TS)
    original_bid_close: Mapped[datetime] = mapped_column(TS)
    forced_close: Mapped[datetime] = mapped_column(TS)
    pickup_date: Mapped[date] = mapped_column(Date)

    trigger_type: Mapped[str] = mapped_column(String(24))
    trigger_window_minutes: Mapped[int] = mapped_column(Integer)  # X
    extension_minutes: Mapped[int] = mapped_column(Integer)  # Y

    extension_count: Mapped[int] = mapped_column(Integer, default=0)
    bid_count: Mapped[int] = mapped_column(Integer, default=0)
    lowest_total: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    l1_supplier_id: Mapped[int | None] = mapped_column(
        ForeignKey("suppliers.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(TS)


class Bid(Base):
    __tablename__ = "bids"

    id: Mapped[int] = mapped_column(primary_key=True)
    rfq_id: Mapped[int] = mapped_column(ForeignKey("rfqs.id", ondelete="CASCADE"))
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))

    freight_charges: Mapped[Decimal] = mapped_column(Money)
    origin_charges: Mapped[Decimal] = mapped_column(Money)
    destination_charges: Mapped[Decimal] = mapped_column(Money)
    total: Mapped[Decimal] = mapped_column(Money)
    transit_days: Mapped[int] = mapped_column(Integer)
    quote_validity_days: Mapped[int] = mapped_column(Integer)

    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TS)


class Standing(Base):
    __tablename__ = "standings"

    rfq_id: Mapped[int] = mapped_column(
        ForeignKey("rfqs.id", ondelete="CASCADE"), primary_key=True
    )
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), primary_key=True)
    best_bid_id: Mapped[int] = mapped_column(ForeignKey("bids.id"))
    best_total: Mapped[Decimal] = mapped_column(Money)
    achieved_at: Mapped[datetime] = mapped_column(TS)
    bid_count: Mapped[int] = mapped_column(Integer, default=1)


class ActivityLog(Base):
    __tablename__ = "activity_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    rfq_id: Mapped[int] = mapped_column(ForeignKey("rfqs.id", ondelete="CASCADE"))
    bid_id: Mapped[int | None] = mapped_column(ForeignKey("bids.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(24))
    message: Mapped[str] = mapped_column(Text)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(TS)
