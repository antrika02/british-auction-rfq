import StatusBadge from "@/components/StatusBadge";
import { formatCountdown, formatDateTime } from "@/lib/format";
import type { RFQ, TriggerType } from "@/lib/types";

const TRIGGER_LABEL: Record<TriggerType, string> = {
  BID_RECEIVED: "Any bid",
  ANY_RANK_CHANGE: "Any rank change",
  L1_CHANGE: "Lowest bidder (L1) change",
};

function Item({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div>
      <div className="text-xs uppercase text-slate-500">{label}</div>
      <div className="text-sm font-medium">{value}</div>
      {note && <div className="text-xs text-amber-700">{note}</div>}
    </div>
  );
}

export default function AuctionHeader({ rfq, serverNow }: { rfq: RFQ; serverNow: number | null }) {
  const startMs = new Date(rfq.bid_start).getTime();
  const closeMs = new Date(rfq.bid_close).getTime();

  let label = "Auction ended";
  let value = rfq.status === "FORCE_CLOSED" ? "Forced close reached" : "Closed";
  let inWindow = false;

  if (rfq.status === "SCHEDULED") {
    label = "Starts in";
    value = serverNow === null ? "..." : formatCountdown(startMs - serverNow);
  } else if (rfq.status === "ACTIVE") {
    label = "Closes in";
    value = serverNow === null ? "..." : formatCountdown(closeMs - serverNow);
    inWindow = serverNow !== null && closeMs - serverNow <= rfq.trigger_window_minutes * 60_000;
  }

  return (
    <div className="rounded-lg bg-white p-5 ring-1 ring-slate-200">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">{rfq.name}</h1>
          <div className="mt-1 flex items-center gap-2 text-sm text-slate-500">
            {rfq.reference_id}
            <StatusBadge status={rfq.status} />
          </div>
        </div>
        <div className="text-right">
          <div className="text-xs uppercase text-slate-500">{label}</div>
          <div className="text-4xl font-bold tabular-nums">{value}</div>
        </div>
      </div>

      {inWindow && (
        <div className="mt-4 rounded-md bg-amber-50 p-3 text-sm text-amber-800">
          <strong>Trigger window is open.</strong> Trigger: {TRIGGER_LABEL[rfq.trigger_type]}. A match adds{" "}
          {rfq.extension_minutes} min, but never past the forced close time.
        </div>
      )}

      <div className="mt-5 grid grid-cols-2 gap-4 border-t border-slate-100 pt-4 sm:grid-cols-4">
        <Item label="Trigger" value={TRIGGER_LABEL[rfq.trigger_type]} />
        <Item label="Window X" value={`${rfq.trigger_window_minutes} min`} />
        <Item label="Extension Y" value={`${rfq.extension_minutes} min`} />
        <Item label="Pickup date" value={rfq.pickup_date} />
        <Item label="Bid start" value={formatDateTime(rfq.bid_start)} />
        <Item label="Original close" value={formatDateTime(rfq.original_bid_close)} />
        <Item
          label="Current close"
          value={formatDateTime(rfq.bid_close)}
          note={rfq.extension_count > 0 ? `extended ${rfq.extension_count}×` : undefined}
        />
        <Item label="Forced close" value={formatDateTime(rfq.forced_close)} />
      </div>
    </div>
  );
}
