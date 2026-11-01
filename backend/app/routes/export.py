import csv
import io
from datetime import timezone

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..errors import AppError
from ..models import RFQ, Bid, Supplier

router = APIRouter(prefix="/api/rfqs", tags=["Export"])

HEADER = [
    "Reference", "Carrier", "Total", "Freight", "Origin", "Destination",
    "Transit days", "Quote validity days", "Placed at (UTC)",
]


def safe(text: str) -> str:
    """Stops Excel from running a carrier name like '=cmd(...)' as a formula."""
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


@router.get("/{rfq_id}/bids.csv")
def export_bids(rfq_id: int, db: Session = Depends(get_db)):
    """Every bid in the auction (not just the first 200 shown on the page), lowest first."""
    rfq = db.get(RFQ, rfq_id)
    if rfq is None:
        raise AppError("RFQ_NOT_FOUND", f"RFQ {rfq_id} not found", 404)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(HEADER)
    rows = db.execute(
        select(Bid, Supplier)
        .join(Supplier, Supplier.id == Bid.supplier_id)
        .where(Bid.rfq_id == rfq_id)
        .order_by(Bid.total, Bid.created_at, Bid.id)
    )
    for bid, supplier in rows:
        writer.writerow([
            safe(rfq.reference_id),
            safe(supplier.name),
            bid.total,
            bid.freight_charges,
            bid.origin_charges,
            bid.destination_charges,
            bid.transit_days,
            bid.quote_validity_days,
            bid.created_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        ])

    filename = rfq.reference_id.replace("/", "-")
    return Response(
        content="\ufeff" + buf.getvalue(),  # the BOM makes Excel read names in UTF-8
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}-bids.csv"'},
    )
