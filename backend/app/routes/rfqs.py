from fastapi import APIRouter, Depends, Query, Response
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from ..broker import broker
from ..clock import get_clock
from ..db import get_db
from ..queries import get_detail, list_rfqs
from ..schemas import (
    AuctionStatus,
    BidCreate,
    BidResult,
    RFQCreate,
    RFQDetail,
    RFQOut,
    RFQPage,
)
from ..services import create_rfq, place_bid, to_out

router = APIRouter(prefix="/api/rfqs", tags=["RFQs"])


@router.post("", response_model=RFQOut, status_code=201)
async def create(data: RFQCreate, db: Session = Depends(get_db), clock=Depends(get_clock)):
    now = clock()
    rfq = await run_in_threadpool(create_rfq, db, data, now)
    out = to_out(rfq, now)
    await broker.publish("rfqs", {"type": "rfq_created", "rfq": out.model_dump(mode="json")})
    return out


@router.get("", response_model=RFQPage)
def listing(
    status: AuctionStatus | None = None,
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    clock=Depends(get_clock),
):
    now = clock()
    rows, total = list_rfqs(db, now, status, q, limit, offset)
    return RFQPage(
        items=[to_out(r, now) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
        server_time=now,
    )


@router.get("/{rfq_id}", response_model=RFQDetail)
def details(rfq_id: int, db: Session = Depends(get_db), clock=Depends(get_clock)):
    return get_detail(db, rfq_id, clock())


@router.post("/{rfq_id}/bids", response_model=BidResult, status_code=201)
async def submit_bid(
    rfq_id: int,
    data: BidCreate,
    response: Response,
    db: Session = Depends(get_db),
    clock=Depends(get_clock),
):
    now = clock()
    result = await run_in_threadpool(place_bid, db, rfq_id, data, now)

    if result.duplicate:
        response.status_code = 200  # not a new bid, so not "201 Created"
    else:
        # Tell every browser watching this auction (and the listing page)
        detail = await run_in_threadpool(get_detail, db, rfq_id, now)
        await broker.publish(
            f"rfq:{rfq_id}",
            {"type": "bid_placed", "detail": detail.model_dump(mode="json")},
        )
        await broker.publish(
            "rfqs",
            {"type": "rfq_updated", "rfq": result.rfq.model_dump(mode="json")},
        )
    return result
