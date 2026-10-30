import secrets
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .errors import AppError
from .extension import analyse_ranking, decide_extension, TriggerType
from .models import RFQ, ActivityLog, Bid, Standing, Supplier
from .schemas import (
    AuctionStatus,
    BidCreate,
    BidOut,
    BidResult,
    RFQCreate,
    RFQOut,
)


# ---------- RFQ ----------
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
        db.flush()
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


# ---------- Bidding ----------
def _ranked(db: Session, rfq_id: int) -> list[Standing]:
    """The leaderboard: lowest price first. A tie goes to whoever got there first."""
    return list(
        db.scalars(
            select(Standing)
            .where(Standing.rfq_id == rfq_id)
            .order_by(Standing.best_total, Standing.achieved_at, Standing.supplier_id)
        )
    )


def _get_or_create_supplier(db: Session, name: str, now: datetime) -> Supplier:
    clean = " ".join(name.split())
    key = clean.casefold()
    supplier = db.scalar(select(Supplier).where(Supplier.name_key == key))
    if supplier:
        return supplier
    try:
        with db.begin_nested():  # a mini-transaction, so a clash doesn't ruin the bid
            supplier = Supplier(name=clean, name_key=key, created_at=now)
            db.add(supplier)
            db.flush()
    except IntegrityError:  # someone created it a split second before us
        supplier = db.scalar(select(Supplier).where(Supplier.name_key == key))
    return supplier


def _bid_out(bid: Bid, supplier_name: str) -> BidOut:
    return BidOut(
        id=bid.id,
        supplier=supplier_name,
        freight_charges=bid.freight_charges,
        origin_charges=bid.origin_charges,
        destination_charges=bid.destination_charges,
        total=bid.total,
        transit_days=bid.transit_days,
        quote_validity_days=bid.quote_validity_days,
        created_at=bid.created_at,
    )


def place_bid(db: Session, rfq_id: int, data: BidCreate, now: datetime) -> BidResult:
    # 1. Lock this auction's row. A second bid at the same moment waits here.
    rfq = db.scalar(select(RFQ).where(RFQ.id == rfq_id).with_for_update())
    if rfq is None:
        raise AppError("RFQ_NOT_FOUND", f"RFQ {rfq_id} not found", 404)

    # 2. Is the auction open?
    if now < rfq.bid_start:
        raise AppError("AUCTION_NOT_STARTED", "This auction has not started yet", 409)
    if now >= rfq.bid_close:
        raise AppError("AUCTION_CLOSED", "This auction is closed. No more bids are accepted", 409)

    # Retried request? Return the original result instead of bidding twice.
    if data.idempotency_key:
        existing = db.scalar(
            select(Bid).where(Bid.rfq_id == rfq.id, Bid.idempotency_key == data.idempotency_key)
        )
        if existing:
            supplier = db.get(Supplier, existing.supplier_id)
            ranked = _ranked(db, rfq.id)
            rank = next((i + 1 for i, s in enumerate(ranked) if s.supplier_id == existing.supplier_id), 0)
            return BidResult(
                bid=_bid_out(existing, supplier.name),
                duplicate=True,
                rank=rank,
                extended=False,
                previous_close=rfq.bid_close,
                new_close=rfq.bid_close,
                reason="Duplicate request: returning the original bid",
                rfq=to_out(rfq, now),
            )

    supplier = _get_or_create_supplier(db, data.carrier_name, now)
    total = data.total

    # 3. A supplier may only improve (lower) their own price.
    standing = db.get(Standing, (rfq.id, supplier.id))
    if standing and total >= standing.best_total:
        raise AppError(
            "BID_NOT_LOWER",
            f"Your new total ({total:.2f}) must be lower than your current best ({standing.best_total})",
            422,
        )

    # 4. Ranking before and after this bid.
    before = [s.supplier_id for s in _ranked(db, rfq.id)]

    bid = Bid(
        rfq_id=rfq.id,
        supplier_id=supplier.id,
        freight_charges=data.freight_charges,
        origin_charges=data.origin_charges,
        destination_charges=data.destination_charges,
        total=total,
        transit_days=data.transit_days,
        quote_validity_days=data.quote_validity_days,
        idempotency_key=data.idempotency_key,
        created_at=now,
    )
    db.add(bid)
    db.flush()  # gives the bid its id

    if standing:
        standing.best_bid_id = bid.id
        standing.best_total = total
        standing.achieved_at = now
        standing.bid_count += 1
    else:
        db.add(
            Standing(
                rfq_id=rfq.id,
                supplier_id=supplier.id,
                best_bid_id=bid.id,
                best_total=total,
                achieved_at=now,
                bid_count=1,
            )
        )
    db.flush()

    ranked = _ranked(db, rfq.id)
    after = [s.supplier_id for s in ranked]

    # 5. The big question: does this bid extend the auction?
    decision = decide_extension(
        now=now,
        bid_close=rfq.bid_close,
        forced_close=rfq.forced_close,
        trigger_type=TriggerType(rfq.trigger_type),
        window_minutes=rfq.trigger_window_minutes,
        extension_minutes=rfq.extension_minutes,
        effect=analyse_ranking(before, after),
    )

    # 6. Update the auction.
    previous_close = rfq.bid_close
    rfq.bid_count += 1
    rfq.lowest_total = ranked[0].best_total
    rfq.l1_supplier_id = ranked[0].supplier_id
    if decision.extended:
        rfq.bid_close = decision.new_close
        rfq.extension_count += 1

    # 7. Activity log: what happened, and why.
    rank_before = before.index(supplier.id) + 1 if supplier.id in before else None
    rank_after = after.index(supplier.id) + 1
    db.add(
        ActivityLog(
            rfq_id=rfq.id,
            bid_id=bid.id,
            kind="BID_PLACED",
            message=f"{supplier.name} bid {total} (now rank L{rank_after})",
            details={
                "supplier": supplier.name,
                "total": str(total),
                "rank_before": rank_before,
                "rank_after": rank_after,
                "in_trigger_window": decision.in_window,
            },
            created_at=now,
        )
    )
    if decision.extended:
        minutes = f"{decision.added_seconds / 60:g}"
        db.add(
            ActivityLog(
                rfq_id=rfq.id,
                bid_id=bid.id,
                kind="EXTENSION",
                message=f"Auction extended by {minutes} min: {decision.reason}",
                details={
                    "from": previous_close.isoformat(),
                    "to": decision.new_close.isoformat(),
                    "trigger": rfq.trigger_type,
                    "capped_by_forced_close": decision.capped,
                },
                created_at=now,
            )
        )
    elif decision.condition_met:  # triggered, but the forced close blocked it
        db.add(
            ActivityLog(
                rfq_id=rfq.id,
                bid_id=bid.id,
                kind="EXTENSION_BLOCKED",
                message=decision.reason,
                details={"forced_close": rfq.forced_close.isoformat()},
                created_at=now,
            )
        )

    db.commit()  # 8. Everything is saved together, or not at all.

    return BidResult(
        bid=_bid_out(bid, supplier.name),
        duplicate=False,
        rank=rank_after,
        extended=decision.extended,
        previous_close=previous_close,
        new_close=rfq.bid_close,
        reason=decision.reason,
        rfq=to_out(rfq, now),
    )
