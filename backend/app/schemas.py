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
