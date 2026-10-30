import secrets
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .errors import AppError
from .models import RFQ, ActivityLog
from .schemas import AuctionStatus, RFQCreate, RFQOut


def compute_status(rfq: RFQ, now: datetime) -> AuctionStatus:
    """Status is calculated, never stored, so it can't go stale."""
    if now < rfq.bid_start:
        return AuctionStatus.SCHEDULED
    if now < rfq.bid_close:
        return AuctionStatus.ACTIVE
    if rfq.bid_close >= rfq.forced_close:
        return AuctionStatus.FORCE_CLOSED
    return AuctionStatus.CLOSED


def to_out(rfq: RFQ, now: datetime) -> RFQOut:
    return RFQOut(
        id=rfq.id,
        reference_id=rfq.reference_id,
        name=rfq.name,
        status=compute_status(rfq, now),
        bid_start=rfq.bid_start,
        bid_close=rfq.bid_close,
        original_bid_close=rfq.original_bid_close,
        forced_close=rfq.forced_close,
        pickup_date=rfq.pickup_date,
        trigger_type=rfq.trigger_type,
        trigger_window_minutes=rfq.trigger_window_minutes,
        extension_minutes=rfq.extension_minutes,
        bid_count=rfq.bid_count,
        extension_count=rfq.extension_count,
        lowest_bid=rfq.lowest_total,
        created_at=rfq.created_at,
    )


def create_rfq(db: Session, data: RFQCreate, now: datetime) -> RFQ:
    if data.bid_close <= now:
        raise AppError("INVALID_TIMES", "Bid close time must be in the future", 422)

    reference_id = data.reference_id or f"RFQ-{now:%Y%m%d}-{secrets.token_hex(2).upper()}"

    rfq = RFQ(
        reference_id=reference_id,
        name=data.name.strip(),
        bid_start=data.bid_start,
        bid_close=data.bid_close,
        original_bid_close=data.bid_close,
        forced_close=data.forced_close,
        pickup_date=data.pickup_date,
        trigger_type=data.trigger_type.value,
        trigger_window_minutes=data.trigger_window_minutes,
        extension_minutes=data.extension_minutes,
        extension_count=0,
        bid_count=0,
        created_at=now,
    )
    db.add(rfq)
    try:
        db.flush()  # gets the new id, and triggers the unique check
    except IntegrityError:
        db.rollback()
        raise AppError("DUPLICATE_REFERENCE", f"Reference ID '{reference_id}' already exists", 409)

    db.add(
        ActivityLog(
            rfq_id=rfq.id,
            kind="RFQ_CREATED",
            message=f"RFQ {reference_id} created",
            details={},
            created_at=now,
        )
    )
    db.commit()
    return rfq


def get_rfq(db: Session, rfq_id: int) -> RFQ:
    rfq = db.get(RFQ, rfq_id)
    if rfq is None:
        raise AppError("RFQ_NOT_FOUND", f"RFQ {rfq_id} not found", 404)
    return rfq
