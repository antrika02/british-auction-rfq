import { formatMoney } from "@/lib/format";
import type { Bid } from "@/lib/types";

export default function BidsTable({ bids }: { bids: Bid[] }) {
  return (
    <div className="rounded-lg bg-white ring-1 ring-slate-200">
      <h2 className="border-b border-slate-100 px-5 py-3 font-semibold">
        All bids <span className="text-sm font-normal text-slate-500">(lowest first)</span>
      </h2>
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
    </div>
  );
}
