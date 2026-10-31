"""Fills the database with demo auctions in every state.

Usage (from the backend folder):
    python scripts/seed.py            # add the demo auctions
    python scripts/seed.py --reset    # delete old demo auctions first, then add fresh ones
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.errors import AppError  # noqa: E402
from app.models import RFQ  # noqa: E402
from app.schemas import BidCreate, RFQCreate  # noqa: E402
from app.services import create_rfq, place_bid  # noqa: E402

now = datetime.now(timezone.utc).replace(microsecond=0)


def T(minutes: int) -> datetime:
    """A moment `minutes` from now (negative means in the past)."""
    return now + timedelta(minutes=minutes)


# Times are minutes from now. Each bid is (minute, carrier, total).
SCENARIOS = [
    {
        "ref": "SEED-CLOSED-001",
        "name": "Delhi to Mumbai (closed after 3 extensions)",
        "created": -200, "start": -190, "close": -120, "forced": -90,
        "trigger": "L1_CHANGE", "x": 10, "y": 5,
        "bids": [
            (-150, "Alpha Logistics", 1500),  # too early: nothing happens
            (-125, "Beta Cargo", 1450),       # takes the lead inside the window: extends
            (-118, "Gamma Lines", 1400),      # takes the lead again: extends
            (-112, "Alpha Logistics", 1350),  # and again: extends
        ],
    },
    {
        "ref": "SEED-FORCED-001",
        "name": "Chennai to Kolkata (reached the forced close time)",
        "created": -120, "start": -110, "close": -60, "forced": -45,
        "trigger": "BID_RECEIVED", "x": 15, "y": 10,
        "bids": [
            (-70, "Alpha Logistics", 2000),  # extends by 10 min
            (-55, "Beta Cargo", 1950),       # would add 10, but is cut at the forced close
            (-47, "Alpha Logistics", 1900),  # triggers, but there is no room left
        ],
    },
    {
        "ref": "SEED-ACTIVE-001",
        "name": "Pune to Hyderabad (closing soon, try a bid!)",
        "created": -30, "start": -25, "close": 12, "forced": 40,
        "trigger": "L1_CHANGE", "x": 10, "y": 5,
        "bids": [
            (-15, "Alpha Logistics", 3200),
            (-5, "Beta Cargo", 3100),
        ],
    },
    {
        "ref": "SEED-SCHEDULED-001",
        "name": "Jaipur to Ahmedabad (starts in 1 hour)",
        "created": -5, "start": 60, "close": 120, "forced": 150,
        "trigger": "ANY_RANK_CHANGE", "x": 10, "y": 5,
        "bids": [],
    },
]


def seed_one(db, sc) -> None:
    data = RFQCreate(
        reference_id=sc["ref"],
        name=sc["name"],
        bid_start=T(sc["start"]),
        bid_close=T(sc["close"]),
        forced_close=T(sc["forced"]),
        pickup_date=(now + timedelta(days=3)).date(),
        trigger_type=sc["trigger"],
        trigger_window_minutes=sc["x"],
        extension_minutes=sc["y"],
    )
    try:
        rfq = create_rfq(db, data, T(sc["created"]))
    except AppError as e:
        if e.code == "DUPLICATE_REFERENCE":
            print(f"skipped {sc['ref']} (already exists, use --reset)")
            return
        raise
    print(f"created {sc['ref']}: {sc['name']}")

    for minute, carrier, total in sc["bids"]:
        freight = total * 70 // 100
        origin = total * 20 // 100
        res = place_bid(
            db,
            rfq.id,
            BidCreate(
                carrier_name=carrier,
                freight_charges=freight,
                origin_charges=origin,
                destination_charges=total - freight - origin,
                transit_days=3,
                quote_validity_days=7,
            ),
            T(minute),
        )
        print(f"   {carrier} bid {total}: L{res.rank}, extended={res.extended}")


def main() -> None:
    with SessionLocal() as db:
        if "--reset" in sys.argv:
            db.execute(delete(RFQ).where(RFQ.reference_id.like("SEED-%")))
            db.commit()
            print("deleted old demo auctions")
        for sc in SCENARIOS:
            seed_one(db, sc)


main()
