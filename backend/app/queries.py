from datetime import datetime

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from .models import RFQ, ActivityLog, Bid, Standing, Supplier
from .schemas import (
    ActivityOut,
    AuctionStatus,
    RFQDetail,
    RankingEntry,
)
from .services import _bid_out, get_rfq, to_out


def list_rfqs(
    db: Session,
    now: datetime,
    status: AuctionStatus | None,
    q: str | None,
    limit: int,
    offset: int,
) -> tuple[list[RFQ], int]:
    conds = []

    # Status is worked out from the times, the same rules as compute_status()
    if status == AuctionStatus.SCHEDULED:
        conds.append(RFQ.bid_start > now)
    elif status == AuctionStatus.ACTIVE:
        conds.append(and_(RFQ.bid_start <= now, RFQ.bid_close > now))
    elif status == AuctionStatus.FORCE_CLOSED:
        conds.append(and_(RFQ.bid_close <= now, RFQ.bid_close >= RFQ.forced_close))
    elif status == AuctionStatus.CLOSED:
        conds.append(and_(RFQ.bid_close <= now, RFQ.bid_close < RFQ.forced_close))

    if q:
        like = f"%{q.strip()}%"
        conds.append(or_(RFQ.name.ilike(like), RFQ.reference_id.ilike(like)))

    total = db.scalar(select(func.count()).select_from(RFQ).where(*conds)) or 0

    # Active auctions first, then scheduled, then finished. Newest first inside each.
    priority = case(
        (and_(RFQ.bid_start <= now, RFQ.bid_close > now), 0),
        (RFQ.bid_start > now, 1),
        else_=2,
    )
    rows = db.scalars(
        select(RFQ)
        .where(*conds)
        .order_by(priority, RFQ.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return list(rows), total


def get_detail(db: Session, rfq_id: int, now: datetime) -> RFQDetail:
    rfq = get_rfq(db, rfq_id)

    # Ranking: one row per supplier, using their best bid
    ranked = db.execute(
        select(Standing, Bid, Supplier)
        .join(Bid, Bid.id == Standing.best_bid_id)
        .join(Supplier, Supplier.id == Standing.supplier_id)
        .where(Standing.rfq_id == rfq_id)
        .order_by(Standing.best_total, Standing.achieved_at, Standing.supplier_id)
    ).all()
    ranking = [
        RankingEntry(
            rank=i + 1,
            label=f"L{i + 1}",
            supplier=supplier.name,
            bid=_bid_out(bid, supplier.name),
            bid_count=standing.bid_count,
        )
        for i, (standing, bid, supplier) in enumerate(ranked)
    ]

    # Every bid, cheapest first (capped at 200 so a huge auction can't slow the page)
    bid_rows = db.execute(
        select(Bid, Supplier)
        .join(Supplier, Supplier.id == Bid.supplier_id)
        .where(Bid.rfq_id == rfq_id)
        .order_by(Bid.total, Bid.created_at)
        .limit(200)
    ).all()
    bids = [_bid_out(bid, supplier.name) for bid, supplier in bid_rows]

    # Activity log, newest first
    log_rows = db.scalars(
        select(ActivityLog)
        .where(ActivityLog.rfq_id == rfq_id)
        .order_by(ActivityLog.id.desc())
        .limit(100)
    ).all()
    activity = [
        ActivityOut(
            id=a.id, kind=a.kind, message=a.message, details=a.details, created_at=a.created_at
        )
        for a in log_rows
    ]

    return RFQDetail(
        rfq=to_out(rfq, now),
        ranking=ranking,
        bids=bids,
        activity=activity,
        server_time=now,
    )
