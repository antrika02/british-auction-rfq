import { formatDateTime } from "@/lib/format";
import type { RFQ } from "@/lib/types";

function Legend({ color, label, time }: { color: string; label: string; time: string }) {
  return (
    <div className="flex items-start gap-2">
      <span className={`mt-1 h-3 w-3 shrink-0 rounded-sm ${color}`} />
      <div>
        <div className="text-xs uppercase text-slate-500">{label}</div>
        <div className="text-sm font-medium">{time}</div>
      </div>
    </div>
  );
}

export default function TimelineBar({ rfq, serverNow }: { rfq: RFQ; serverNow: number | null }) {
  const start = new Date(rfq.bid_start).getTime();
  const original = new Date(rfq.original_bid_close).getTime();
  const close = new Date(rfq.bid_close).getTime();
  const forced = new Date(rfq.forced_close).getTime();

  // Position on the bar, as a percentage of start -> forced close
  const span = forced - start;
  const at = (t: number) => Math.max(0, Math.min(100, ((t - start) / span) * 100));

  const nowPct = serverNow === null ? null : ((serverNow - start) / span) * 100;
  const showNow = nowPct !== null && nowPct >= 0 && nowPct <= 100;

  const extendedMin = Math.round((close - original) / 60000);
  const availableMin = Math.round((forced - original) / 60000);

  return (
    <div className="rounded-lg bg-white p-5 ring-1 ring-slate-200">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-semibold">Timeline</h2>
        <span className="text-sm text-slate-600">
          Extended <strong>{extendedMin} min</strong> of {availableMin} min possible
        </span>
      </div>

      <div className="relative h-4 rounded-full bg-slate-200">
        {/* Planned bidding time */}
        <div
          className="absolute left-0 top-0 h-full rounded-l-full bg-blue-500"
          style={{ width: `${at(original)}%` }}
        />
        {/* Time added by extensions */}
        <div
          className="absolute top-0 h-full bg-amber-400"
          style={{ left: `${at(original)}%`, width: `${at(close) - at(original)}%` }}
        />
        {/* Where we are right now */}
        {showNow && (
          <div
            className="absolute -top-1 h-6 w-0.5 bg-red-600"
            style={{ left: `${nowPct}%` }}
            title="Now"
          />
        )}
      </div>
      <div className="mt-1 flex justify-between text-[10px] uppercase text-slate-400">
        <span>Start</span>
        <span>Forced close</span>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Legend color="bg-slate-300" label="Bid start" time={formatDateTime(rfq.bid_start)} />
        <Legend color="bg-blue-500" label="Original close" time={formatDateTime(rfq.original_bid_close)} />
        <Legend color="bg-amber-400" label="Current close" time={formatDateTime(rfq.bid_close)} />
        <Legend color="bg-slate-200 ring-1 ring-slate-400" label="Forced close" time={formatDateTime(rfq.forced_close)} />
      </div>
      {showNow && (
        <p className="mt-3 text-xs text-slate-500">
          <span className="mr-1 inline-block h-2.5 w-0.5 bg-red-600 align-middle" />
          The red line is the current time.
        </p>
      )}
    </div>
  );
}
