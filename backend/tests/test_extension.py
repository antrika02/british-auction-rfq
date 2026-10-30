from datetime import datetime, timedelta, timezone

from app.extension import (
    RankEffect,
    TriggerType,
    analyse_ranking,
    decide_extension,
    in_trigger_window,
)


def at(h, m, s=0):
    return datetime(2026, 10, 30, h, m, s, tzinfo=timezone.utc)


CLOSE = at(18, 0)    # 6:00 PM
FORCED = at(18, 8)   # 6:08 PM


def run(now, trigger=TriggerType.BID_RECEIVED, rank=False, l1=False,
        close=CLOSE, forced=FORCED, x=10, y=5):
    return decide_extension(
        now=now, bid_close=close, forced_close=forced,
        trigger_type=trigger, window_minutes=x, extension_minutes=y,
        effect=RankEffect(rank_changed=rank, l1_changed=l1),
    )


# ---------- the trigger window ----------
def test_bid_before_window_does_not_extend():
    d = run(at(17, 49, 59))
    assert not d.in_window and not d.extended
    assert d.new_close == CLOSE


def test_window_start_is_inclusive():
    assert in_trigger_window(at(17, 50, 0), CLOSE, 10)
    assert run(at(17, 50, 0)).new_close == at(18, 5)


def test_bid_at_exact_close_is_not_in_window():
    assert not in_trigger_window(CLOSE, CLOSE, 10)


# ---------- trigger a: any bid ----------
def test_any_bid_in_window_extends_by_y():
    d = run(at(17, 55))
    assert d.extended and d.new_close == at(18, 5)
    assert d.added_seconds == 300


# ---------- trigger b: any rank change ----------
def test_rank_trigger_needs_rank_change():
    assert not run(at(17, 58), TriggerType.ANY_RANK_CHANGE, rank=False).extended
    assert run(at(17, 58), TriggerType.ANY_RANK_CHANGE, rank=True).extended


# ---------- trigger c: L1 change ----------
def test_l1_trigger_ignores_other_rank_changes():
    d = run(at(17, 59), TriggerType.L1_CHANGE, rank=True, l1=False)
    assert not d.extended and d.in_window and not d.condition_met


def test_l1_trigger_extends_when_l1_changes():
    assert run(at(17, 59), TriggerType.L1_CHANGE, rank=True, l1=True).extended


# ---------- the forced close cap ----------
def test_extension_is_shortened_by_forced_close():
    # close is 6:05, +5 would be 6:10 but forced close is 6:08
    d = run(at(18, 3), close=at(18, 5))
    assert d.extended and d.capped
    assert d.new_close == FORCED


def test_no_extension_when_already_at_forced_close():
    d = run(at(18, 7), close=FORCED)
    assert not d.extended and d.capped
    assert d.new_close == FORCED


def test_close_time_can_never_pass_forced_close():
    # A bid arrives one second before every close time, 50 times in a row.
    close = CLOSE
    for _ in range(50):
        d = run(close - timedelta(seconds=1), close=close)
        close = d.new_close
        assert close <= FORCED
    assert close == FORCED


# ---------- ranking comparison ----------
def test_same_ranking_means_no_change():
    e = analyse_ranking([1, 2, 3], [1, 2, 3])
    assert not e.rank_changed and not e.l1_changed


def test_swap_of_first_two_changes_rank_and_l1():
    e = analyse_ranking([1, 2, 3], [2, 1, 3])
    assert e.rank_changed and e.l1_changed


def test_swap_of_lower_ranks_does_not_change_l1():
    e = analyse_ranking([1, 2, 3], [1, 3, 2])
    assert e.rank_changed and not e.l1_changed


def test_first_ever_bid_counts_as_l1_change():
    e = analyse_ranking([], [7])
    assert e.rank_changed and e.l1_changed


def test_new_supplier_at_the_bottom_is_a_rank_change_but_not_l1():
    e = analyse_ranking([1, 2], [1, 2, 3])
    assert e.rank_changed and not e.l1_changed
