from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, Field, model_validator

from .extension import TriggerType


class AuctionStatus(StrEnum):
    SCHEDULED = "SCHEDULED"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    FORCE_CLOSED = "FORCE_CLOSED"


class RFQCreate(BaseModel):
    reference_id: str | None = Field(
        default=None, min_length=3, max_length=64, pattern=r"^[A-Za-z0-9._/\-]+$"
    )
    name: str = Field(min_length=3, max_length=200)
    bid_start: AwareDatetime
    bid_close: AwareDatetime
    forced_close: AwareDatetime
    pickup_date: date
    trigger_type: TriggerType = TriggerType.BID_RECEIVED
    trigger_window_minutes: int = Field(ge=1, le=1440)  # X
    extension_minutes: int = Field(ge=1, le=1440)  # Y

    @model_validator(mode="after")
    def check_times(self):
        if self.bid_close <= self.bid_start:
            raise ValueError("Bid close time must be later than bid start time")
        if self.forced_close <= self.bid_close:
            raise ValueError("Forced bid close time must be later than bid close time")
        return self


class RFQOut(BaseModel):
    id: int
    reference_id: str
    name: str
    status: AuctionStatus
    bid_start: datetime
    bid_close: datetime
    original_bid_close: datetime
    forced_close: datetime
    pickup_date: date
    trigger_type: TriggerType
    trigger_window_minutes: int
    extension_minutes: int
    bid_count: int
    extension_count: int
    lowest_bid: Decimal | None
    created_at: datetime


class BidCreate(BaseModel):
    carrier_name: str = Field(min_length=2, max_length=120)
    freight_charges: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    origin_charges: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    destination_charges: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    transit_days: int = Field(ge=1, le=365)
    quote_validity_days: int = Field(ge=1, le=365)
    # Optional: lets a client safely retry the same request without a double bid
    idempotency_key: str | None = Field(default=None, max_length=64)

    @property
    def total(self) -> Decimal:
        return self.freight_charges + self.origin_charges + self.destination_charges

    @model_validator(mode="after")
    def check_total(self):
        if self.total <= 0:
            raise ValueError("The total quote must be greater than zero")
        return self


class BidOut(BaseModel):
    id: int
    supplier: str
    freight_charges: Decimal
    origin_charges: Decimal
    destination_charges: Decimal
    total: Decimal
    transit_days: int
    quote_validity_days: int
    created_at: datetime


class BidResult(BaseModel):
    bid: BidOut
    duplicate: bool
    rank: int  # 1 means L1
    extended: bool
    previous_close: datetime
    new_close: datetime
    reason: str
    rfq: RFQOut


class RankingEntry(BaseModel):
    rank: int
    label: str  # L1, L2, L3 ...
    supplier: str
    bid: BidOut
    bid_count: int


class ActivityOut(BaseModel):
    id: int
    kind: str
    message: str
    details: dict
    created_at: datetime


class RFQDetail(BaseModel):
    rfq: RFQOut
    ranking: list[RankingEntry]
    bids: list[BidOut]  # every bid, cheapest first
    activity: list[ActivityOut]  # newest first
    server_time: datetime  # lets the browser's countdown use the server's clock


class RFQPage(BaseModel):
    items: list[RFQOut]
    total: int
    limit: int
    offset: int
    server_time: datetime
