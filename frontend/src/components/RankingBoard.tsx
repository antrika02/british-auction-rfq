import { formatMoney } from "@/lib/format";
import type { RankingEntry } from "@/lib/types";

export default function RankingBoard({ ranking }: { ranking: RankingEntry[] }) {
  return (
    <div className="rounded-lg bg-white ring-1 ring-slate-200">
      <h2 className="border-b border-slate-100 px-5 py-3 font-semibold">Ranking</h2>
      {ranking.length === 0 ? (
        <p className="px-5 py-8 text-center text-sm text-slate-500">No bids yet.</p>
      ) : (
        <ul className="divide-y divide-slate-100">
          {ranking.map((r) => (
            <li key={r.supplier} className="flex flex-wrap items-center gap-4 px-5 py-4">
              <span
                className={`flex h-10 w-10 items-center justify-center rounded-full text-sm font-bold ${
                  r.rank === 1 ? "bg-green-100 text-green-800" : "bg-slate-100 text-slate-700"
                }`}
              >
                {r.label}
              </span>
              <div className="min-w-40 flex-1">
                <div className="font-medium">{r.supplier}</div>
                <div className="text-xs text-slate-500">
                  {r.bid_count} bid{r.bid_count === 1 ? "" : "s"} · {r.bid.transit_days} days transit · valid{" "}
                  {r.bid.quote_validity_days} days
                </div>
              </div>
              <div className="text-xs text-slate-500">
                Freight {formatMoney(r.bid.freight_charges)}
                <br />
                Origin {formatMoney(r.bid.origin_charges)} · Dest. {formatMoney(r.bid.destination_charges)}
              </div>
              <div className="text-right text-xl font-bold tabular-nums">{formatMoney(r.bid.total)}</div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
