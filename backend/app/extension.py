"""British Auction extension rules.

Pure functions: no database, no clock. `now` is always passed in,
so every rule can be tested with exact timestamps.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum


class TriggerType(StrEnum):
    BID_RECEIVED = "BID_RECEIVED"        # any bid in the last X minutes
    ANY_RANK_CHANGE = "ANY_RANK_CHANGE"  # any supplier's rank changed
    L1_CHANGE = "L1_CHANGE"              # the lowest bidder changed


TRIGGER_LABELS = {
    TriggerType.BID_RECEIVED: "A bid was received",
    TriggerType.ANY_RANK_CHANGE: "A supplier's rank changed",
    TriggerType.L1_CHANGE: "The lowest bidder (L1) changed",
}


@dataclass(frozen=True)
class RankEffect:
    rank_changed: bool
    l1_changed: bool


def analyse_ranking(before: Sequence[int], after: Sequence[int]) -> RankEffect:
    """Compare two rankings (lists of supplier ids, best price first).

    rank_changed: the order is different in any way. A supplier appearing
                  for the first time also counts (it adds a new rank).
    l1_changed:   the supplier in first place is different. The very first
                  bid of an auction counts (nobody -> somebody).
    """
    before_l1 = before[0] if before else None
    after_l1 = after[0] if after else None
    return RankEffect(
        rank_changed=list(before) != list(after),
        l1_changed=before_l1 != after_l1,
    )


@dataclass(frozen=True)
class ExtensionDecision:
    in_window: bool       # was the bid inside the last X minutes?
    condition_met: bool   # did the chosen trigger happen?
    extended: bool        # did the close time actually move?
    capped: bool          # did the forced close shorten or block it?
    new_close: datetime
    added_seconds: int
    reason: str           # shown in the activity log


def in_trigger_window(now: datetime, bid_close: datetime, window_minutes: int) -> bool:
    """True from (close - X) up to, but not including, the close time."""
    return bid_close - timedelta(minutes=window_minutes) <= now < bid_close


def decide_extension(
    *,
    now: datetime,
    bid_close: datetime,
    forced_close: datetime,
    trigger_type: TriggerType,
    window_minutes: int,   # X
    extension_minutes: int,  # Y
    effect: RankEffect,
) -> ExtensionDecision:
    """Decide if a bid placed at `now` extends the auction.

    The rule that must never break:  new_close <= forced_close
    """
    # 1. Outside the last X minutes: nothing happens.
    if not in_trigger_window(now, bid_close, window_minutes):
        return ExtensionDecision(
            in_window=False, condition_met=False, extended=False, capped=False,
            new_close=bid_close, added_seconds=0,
            reason=f"Bid placed outside the last {window_minutes} min trigger window",
        )

    # 2. Inside the window: did the chosen trigger happen?
    condition_met = {
        TriggerType.BID_RECEIVED: True,
        TriggerType.ANY_RANK_CHANGE: effect.rank_changed,
        TriggerType.L1_CHANGE: effect.l1_changed,
    }[trigger_type]

    if not condition_met:
        return ExtensionDecision(
            in_window=True, condition_met=False, extended=False, capped=False,
            new_close=bid_close, added_seconds=0,
            reason=f"Bid inside the trigger window, but the {trigger_type.value} condition was not met",
        )

    # 3. Add Y minutes, but never go past the forced close.
    target = bid_close + timedelta(minutes=extension_minutes)
    new_close = min(target, forced_close)
    capped = target > forced_close
    added = int((new_close - bid_close).total_seconds())
    reason = f"{TRIGGER_LABELS[trigger_type]} in the last {window_minutes} min before close"

    if added <= 0:  # already sitting at the forced close
        return ExtensionDecision(
            in_window=True, condition_met=True, extended=False, capped=True,
            new_close=bid_close, added_seconds=0,
            reason=reason + ", but the auction is already at its forced close time",
        )

    if capped:
        reason += " (shortened to stop at the forced close time)"
    return ExtensionDecision(
        in_window=True, condition_met=True, extended=True, capped=capped,
        new_close=new_close, added_seconds=added, reason=reason,
    )
