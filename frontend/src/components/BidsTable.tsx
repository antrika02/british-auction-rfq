import { API_URL } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import type { Bid } from "@/lib/types";

export default function BidsTable({ rfqId, bids }: { rfqId: number; bids: Bid[] }) {
  return (
    <div className="rounded-lg bg-white ring-1 ring-slate-200">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-5 py-3">
        <h2 className="font-semibold">
          All bids <span className="text-sm font-normal text-slate-500">(lowest first)</span>
        </h2>
        <a
          href={`${API_URL}/api/rfqs/${rfqId}/bids.csv`}
          className="rounded-md px-3 py-1 text-sm ring-1 ring-slate-300 hover:bg-slate-100"
        >
          Download CSV
        </a>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-2">Carrier</th>
              <th className="px-4 py-2 text-right">Total</th>
              <th className="px-4 py-2 text-right">Freight</th>
              <th className="px-4 py-2 text-right">Origin</th>
              <th className="px-4 py-2 text-right">Destination</th>
              <th className="px-4 py-2">Transit</th>
              <th className="px-4 py-2">Valid</th>
              <th className="px-4 py-2">Placed at</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {bids.length === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-6 text-center text-slate-500">
                  No bids yet.
                </td>
              </tr>
            )}
            {bids.map((b) => (
              <tr key={b.id}>
                <td className="px-4 py-2 font-medium">{b.supplier}</td>
                <td className="px-4 py-2 text-right font-semibold tabular-nums">{formatMoney(b.total)}</td>
                <td className="px-4 py-2 text-right tabular-nums">{formatMoney(b.freight_charges)}</td>
                <td className="px-4 py-2 text-right tabular-nums">{formatMoney(b.origin_charges)}</td>
                <td className="px-4 py-2 text-right tabular-nums">{formatMoney(b.destination_charges)}</td>
                <td className="px-4 py-2">{b.transit_days} d</td>
                <td className="px-4 py-2">{b.quote_validity_days} d</td>
                <td className="px-4 py-2 whitespace-nowrap">
                  {new Date(b.created_at).toLocaleTimeString("en-IN", { timeStyle: "medium" })}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {bids.length >= 200 && (
        <p className="border-t border-slate-100 px-5 py-2 text-xs text-slate-500">
          Showing the 200 lowest bids. The CSV has all of them.
        </p>
      )}
    </div>
  );
}
