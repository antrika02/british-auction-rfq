from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app


def parse(s: str) -> datetime:
    return datetime.fromisoformat(s)


def rfq_body(clock, *, name="Test freight", start_in=-1, close_in=5, forced_in=30,
             trigger="L1_CHANGE", x=60, y=5, reference_id=None):
    body = {
        "name": name,
        "bid_start": (clock.now + timedelta(minutes=start_in)).isoformat(),
        "bid_close": (clock.now + timedelta(minutes=close_in)).isoformat(),
        "forced_close": (clock.now + timedelta(minutes=forced_in)).isoformat(),
        "pickup_date": "2026-11-05",
        "trigger_type": trigger,
        "trigger_window_minutes": x,
        "extension_minutes": y,
    }
    if reference_id:
        body["reference_id"] = reference_id
    return body


def make_rfq(client, clock, **kwargs):
    r = client.post("/api/rfqs", json=rfq_body(clock, **kwargs))
    assert r.status_code == 201, r.text
    return r.json()


def bid(client, rfq_id, carrier, total, **extra):
    payload = {
        "carrier_name": carrier,
        "freight_charges": total,
        "origin_charges": 0,
        "destination_charges": 0,
        "transit_days": 3,
        "quote_validity_days": 7,
        **extra,
    }
    return client.post(f"/api/rfqs/{rfq_id}/bids", json=payload)


def details(client, rfq_id):
    r = client.get(f"/api/rfqs/{rfq_id}")
    assert r.status_code == 200, r.text
    return r.json()


# ---------- creating an RFQ ----------
def test_create_rfq(client, clock):
    rfq = make_rfq(client, clock)
    assert rfq["status"] == "ACTIVE"
    assert rfq["bid_close"] == rfq["original_bid_close"]
    assert rfq["extension_count"] == 0


def test_forced_close_must_be_after_close(client, clock):
    r = client.post("/api/rfqs", json=rfq_body(clock, close_in=10, forced_in=3))
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "Forced bid close" in r.json()["error"]["message"]


def test_close_time_in_the_past_is_rejected(client, clock):
    r = client.post("/api/rfqs", json=rfq_body(clock, start_in=-60, close_in=-5))
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "INVALID_TIMES"


def test_duplicate_reference_id_is_rejected(client, clock):
    make_rfq(client, clock, reference_id="REF-001")
    r = client.post("/api/rfqs", json=rfq_body(clock, reference_id="REF-001"))
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "DUPLICATE_REFERENCE"


# ---------- bidding rules ----------
def test_bid_before_start_is_rejected(client, clock):
    rfq = make_rfq(client, clock, start_in=5, close_in=30, forced_in=60)
    r = bid(client, rfq["id"], "Alpha", 1000)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "AUCTION_NOT_STARTED"


def test_bid_at_exact_close_time_is_rejected(client, clock):
    rfq = make_rfq(client, clock, close_in=5)
    clock.advance(minutes=5)
    r = bid(client, rfq["id"], "Alpha", 1000)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "AUCTION_CLOSED"


def test_supplier_can_only_improve_their_own_bid(client, clock):
    rfq = make_rfq(client, clock)
    assert bid(client, rfq["id"], "Alpha", 1000).status_code == 201
    for total in (1000, 1100):
        r = bid(client, rfq["id"], "Alpha", total)
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "BID_NOT_LOWER"
    assert bid(client, rfq["id"], "Alpha", 900).status_code == 201


def test_supplier_names_are_case_and_space_insensitive(client, clock):
    rfq = make_rfq(client, clock)
    bid(client, rfq["id"], "Alpha Logistics", 1000)
    bid(client, rfq["id"], "  alpha   LOGISTICS ", 900)
    d = details(client, rfq["id"])
    assert len(d["ranking"]) == 1
    assert d["ranking"][0]["bid_count"] == 2


def test_invalid_bid_gives_field_errors(client, clock):
    rfq = make_rfq(client, clock)
    r = bid(client, rfq["id"], "Alpha", -5)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
    assert r.json()["error"]["details"][0]["field"] == "freight_charges"


def test_same_idempotency_key_does_not_bid_twice(client, clock):
    rfq = make_rfq(client, clock)
    first = bid(client, rfq["id"], "Alpha", 1000, idempotency_key="abc-123")
    second = bid(client, rfq["id"], "Alpha", 1000, idempotency_key="abc-123")
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["duplicate"] is True
    assert details(client, rfq["id"])["rfq"]["bid_count"] == 1


def test_tie_goes_to_the_earlier_bid(client, clock):
    rfq = make_rfq(client, clock)
    bid(client, rfq["id"], "Alpha", 1000)
    clock.advance(seconds=30)
    r = bid(client, rfq["id"], "Beta", 1000)
    assert r.json()["rank"] == 2
    assert details(client, rfq["id"])["ranking"][0]["supplier"] == "Alpha"


# ---------- extension rules ----------
def test_first_bid_inside_window_extends(client, clock):
    rfq = make_rfq(client, clock, close_in=5)
    body = bid(client, rfq["id"], "Alpha", 1000).json()
    assert body["rank"] == 1
    assert body["extended"] is True
    assert parse(body["new_close"]) == clock.now + timedelta(minutes=10)


def test_bid_outside_window_does_not_extend(client, clock):
    rfq = make_rfq(client, clock, close_in=90, forced_in=180, x=10)
    body = bid(client, rfq["id"], "Alpha", 1000).json()
    assert body["extended"] is False
    assert "outside" in body["reason"]


def test_l1_trigger_ignores_a_bid_that_is_not_in_the_lead(client, clock):
    rfq = make_rfq(client, clock, trigger="L1_CHANGE")
    bid(client, rfq["id"], "Alpha", 1000)
    body = bid(client, rfq["id"], "Beta", 1500).json()
    assert body["rank"] == 2
    assert body["extended"] is False
    assert "not met" in body["reason"]


def test_l1_trigger_extends_when_the_lead_changes(client, clock):
    rfq = make_rfq(client, clock, trigger="L1_CHANGE")
    bid(client, rfq["id"], "Alpha", 1000)
    body = bid(client, rfq["id"], "Beta", 900).json()
    assert body["rank"] == 1
    assert body["extended"] is True
    assert parse(body["new_close"]) == clock.now + timedelta(minutes=15)


@pytest.mark.parametrize(
    "trigger,expected",
    [("ANY_RANK_CHANGE", True), ("L1_CHANGE", False), ("BID_RECEIVED", True)],
)
def test_swapping_two_lower_ranks(client, clock, trigger, expected):
    # Last bid swaps Beta and Gamma (L2 and L3). L1 stays the same.
    rfq = make_rfq(client, clock, trigger=trigger, forced_in=240)
    bid(client, rfq["id"], "Alpha", 1000)
    bid(client, rfq["id"], "Beta", 1100)
    bid(client, rfq["id"], "Gamma", 1200)
    body = bid(client, rfq["id"], "Gamma", 1050).json()
    assert body["extended"] is expected


def test_any_bid_trigger_extends_even_for_a_worse_bid(client, clock):
    rfq = make_rfq(client, clock, trigger="BID_RECEIVED")
    bid(client, rfq["id"], "Alpha", 1000)
    assert bid(client, rfq["id"], "Beta", 5000).json()["extended"] is True


def test_extension_never_passes_forced_close(client, clock):
    rfq = make_rfq(client, clock, close_in=5, forced_in=8, y=5)
    forced = clock.now + timedelta(minutes=8)

    first = bid(client, rfq["id"], "Alpha", 1000).json()
    assert first["extended"] is True  # +5 would be minute 10, so it stops at minute 8
    assert parse(first["new_close"]) == forced

    second = bid(client, rfq["id"], "Beta", 900).json()  # lead changes, but no room left
    assert second["extended"] is False
    assert "forced close" in second["reason"]

    d = details(client, rfq["id"])
    assert parse(d["rfq"]["bid_close"]) == forced
    assert d["rfq"]["extension_count"] == 1
    assert "EXTENSION_BLOCKED" in [a["kind"] for a in d["activity"]]


# ---------- status ----------
def test_status_becomes_closed(client, clock):
    rfq = make_rfq(client, clock, close_in=5, forced_in=30)
    assert details(client, rfq["id"])["rfq"]["status"] == "ACTIVE"
    clock.advance(minutes=6)
    assert details(client, rfq["id"])["rfq"]["status"] == "CLOSED"


def test_status_becomes_force_closed_and_rejects_bids(client, clock):
    rfq = make_rfq(client, clock, close_in=5, forced_in=8)
    bid(client, rfq["id"], "Alpha", 1000)  # extends to the forced close
    clock.advance(minutes=9)
    assert details(client, rfq["id"])["rfq"]["status"] == "FORCE_CLOSED"
    r = bid(client, rfq["id"], "Beta", 500)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "AUCTION_CLOSED"


# ---------- reading ----------
def test_details_has_ranking_bids_and_activity(client, clock):
    rfq = make_rfq(client, clock)
    bid(client, rfq["id"], "Alpha", 1000)
    bid(client, rfq["id"], "Beta", 900)
    d = details(client, rfq["id"])
    assert [r["label"] for r in d["ranking"]] == ["L1", "L2"]
    assert d["ranking"][0]["supplier"] == "Beta"
    totals = [Decimal(b["total"]) for b in d["bids"]]
    assert totals == sorted(totals)
    ids = [a["id"] for a in d["activity"]]
    assert ids == sorted(ids, reverse=True)  # newest first
    assert "server_time" in d


def test_listing_filter_and_search(client, clock):
    make_rfq(client, clock, name="Delhi to Mumbai")
    make_rfq(client, clock, name="Pune to Goa", start_in=60, close_in=120, forced_in=180)

    everything = client.get("/api/rfqs").json()
    assert everything["total"] == 2

    scheduled = client.get("/api/rfqs", params={"status": "SCHEDULED"}).json()
    assert [i["name"] for i in scheduled["items"]] == ["Pune to Goa"]

    assert client.get("/api/rfqs", params={"q": "delhi"}).json()["total"] == 1
    assert client.get("/api/rfqs", params={"status": "ACTIVE", "q": "pune"}).json()["total"] == 0


# ---------- many bids at once ----------
def test_bids_at_the_same_moment_are_handled_safely(client, clock):
    rfq = make_rfq(client, clock, forced_in=240)
    n = 8

    def worker(i):
        c = TestClient(app)
        return bid(c, rfq["id"], f"Carrier {i}", 1000 - i * 10).status_code

    with ThreadPoolExecutor(max_workers=n) as pool:
        codes = list(pool.map(worker, range(n)))

    assert codes == [201] * n
    d = details(client, rfq["id"])
    assert d["rfq"]["bid_count"] == n
    assert len(d["ranking"]) == n
    totals = [Decimal(r["bid"]["total"]) for r in d["ranking"]]
    assert totals == sorted(totals)
    assert Decimal(d["rfq"]["lowest_bid"]) == Decimal(930)


# ---------- CSV export ----------
def test_csv_export(client, clock):
    rfq = make_rfq(client, clock)
    bid(client, rfq["id"], "Alpha", 1000)
    bid(client, rfq["id"], "=SUM(1+1)", 900)  # a carrier name that looks like a formula

    r = client.get(f"/api/rfqs/{rfq['id']}/bids.csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    lines = r.text.strip().splitlines()
    assert len(lines) == 3  # header + 2 bids
    assert lines[1].split(",")[1] == "'=SUM(1+1)"  # lowest first, formula neutralised


def test_csv_export_of_unknown_auction_is_404(client):
    assert client.get("/api/rfqs/999/bids.csv").status_code == 404
