"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import StatusBadge from "@/components/StatusBadge";
import { listRfqs, WS_URL } from "@/lib/api";
import { formatCountdown, formatDateTime, formatMoney } from "@/lib/format";
import type { AuctionStatus, RFQPage } from "@/lib/types";
import { useNow } from "@/lib/useNow";

const PAGE_SIZE = 10;
const TABS: { label: string; value: AuctionStatus | "" }[] = [
  { label: "All", value: "" },
  { label: "Active", value: "ACTIVE" },
  { label: "Scheduled", value: "SCHEDULED" },
  { label: "Closed", value: "CLOSED" },
  { label: "Force closed", value: "FORCE_CLOSED" },
];

export default function ListingPage() {
  const [status, setStatus] = useState<AuctionStatus | "">("");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<RFQPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [skew, setSkew] = useState(0); // server clock minus browser clock
  const now = useNow();
  const serverNow = now === null ? null : now + skew;

  // Wait 300 ms after typing before searching
  useEffect(() => {
    const id = setTimeout(() => {
      setQuery(search.trim());
      setOffset(0);
    }, 300);
    return () => clearTimeout(id);
  }, [search]);

  const load = useCallback(async () => {
    try {
      const data = await listRfqs({
        status: status || undefined,
        q: query || undefined,
        limit: PAGE_SIZE,
        offset,
      });
      setPage(data);
      setSkew(new Date(data.server_time).getTime() - Date.now());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    }
  }, [status, query, offset]);

  useEffect(() => {
    load();
  }, [load]);

  // Live updates: reload whenever any auction changes
  const loadRef = useRef(load);
  useEffect(() => {
    loadRef.current = load;
  }, [load]);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let timer: ReturnType<typeof setTimeout>;
    let stopped = false;
    const connect = () => {
      ws = new WebSocket(`${WS_URL}/ws/rfqs`);
      ws.onmessage = () => loadRef.current();
      ws.onclose = () => {
        if (!stopped) timer = setTimeout(connect, 2000); // reconnect
      };
    };
    connect();
    return () => {
      stopped = true;
      clearTimeout(timer);
      ws?.close();
    };
  }, []);

  // When an active auction's timer reaches zero, reload so its status updates
  const lastRefresh = useRef(0);
  useEffect(() => {
    if (!page || serverNow === null) return;
    const expired = page.items.some(
      (r) => r.status === "ACTIVE" && new Date(r.bid_close).getTime() <= serverNow,
    );
    if (expired && Date.now() - lastRefresh.current > 3000) {
      lastRefresh.current = Date.now();
      load();
    }
  }, [serverNow, page, load]);

  const total = page?.total ?? 0;
  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + PAGE_SIZE, total);

  return (
    <div>
      <h1 className="mb-4 text-2xl font-semibold">Auctions</h1>

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-1">
          {TABS.map((t) => (
            <button
              key={t.label}
              onClick={() => {
                setStatus(t.value);
                setOffset(0);
              }}
              className={`rounded-md px-3 py-1.5 text-sm ${
                status === t.value
                  ? "bg-slate-900 text-white"
                  : "bg-white text-slate-700 ring-1 ring-slate-200 hover:bg-slate-100"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search name or reference..."
          className="w-64 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm"
        />
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</div>
      )}

      <div className="overflow-x-auto rounded-lg bg-white ring-1 ring-slate-200">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3">RFQ</th>
              <th className="px-4 py-3">Lowest bid</th>
              <th className="px-4 py-3">Current close</th>
              <th className="px-4 py-3">Forced close</th>
              <th className="px-4 py-3">Time left</th>
              <th className="px-4 py-3">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {page === null && !error && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                  Loading...
                </td>
              </tr>
            )}
            {page?.items.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                  No auctions found.
                </td>
              </tr>
            )}
            {page?.items.map((r) => {
              const msLeft = serverNow === null ? null : new Date(r.bid_close).getTime() - serverNow;
              return (
                <tr key={r.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3">
                    <Link href={`/rfqs/${r.id}`} className="font-medium text-blue-700 hover:underline">
                      {r.name}
                    </Link>
                    <div className="text-xs text-slate-500">
                      {r.reference_id} · {r.bid_count} bid{r.bid_count === 1 ? "" : "s"}
                    </div>
                  </td>
                  <td className="px-4 py-3 font-medium tabular-nums">{formatMoney(r.lowest_bid)}</td>
                  <td className="px-4 py-3">
                    {formatDateTime(r.bid_close)}
                    {r.extension_count > 0 && (
                      <div className="text-xs text-amber-700">
                        extended {r.extension_count}×
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3">{formatDateTime(r.forced_close)}</td>
                  <td className="px-4 py-3 tabular-nums">
                    {r.status === "ACTIVE" && msLeft !== null ? formatCountdown(msLeft) : "-"}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={r.status} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="mt-4 flex items-center justify-between text-sm text-slate-600">
        <span>
          {from}-{to} of {total}
        </span>
        <div className="flex gap-2">
          <button
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            className="rounded-md bg-white px-3 py-1.5 ring-1 ring-slate-200 disabled:opacity-40"
          >
            Previous
          </button>
          <button
            disabled={offset + PAGE_SIZE >= total}
            onClick={() => setOffset(offset + PAGE_SIZE)}
            className="rounded-md bg-white px-3 py-1.5 ring-1 ring-slate-200 disabled:opacity-40"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
