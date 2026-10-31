"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef } from "react";
import ActivityLog from "@/components/ActivityLog";
import AuctionHeader from "@/components/AuctionHeader";
import BidsTable from "@/components/BidsTable";
import RankingBoard from "@/components/RankingBoard";
import { useNow } from "@/lib/useNow";
import { useRfqDetail } from "@/lib/useRfqDetail";

export default function AuctionPage() {
  const { id } = useParams<{ id: string }>();
  const { detail, error, skew, live, refresh } = useRfqDetail(id);
  const now = useNow();
  const serverNow = now === null ? null : now + skew;

  // When the clock passes a start or close time, reload so the status updates
  const lastRefresh = useRef(0);
  useEffect(() => {
    if (!detail || serverNow === null) return;
    const { status, bid_start, bid_close } = detail.rfq;
    const due =
      (status === "SCHEDULED" && new Date(bid_start).getTime() <= serverNow) ||
      (status === "ACTIVE" && new Date(bid_close).getTime() <= serverNow);
    if (due && Date.now() - lastRefresh.current > 3000) {
      lastRefresh.current = Date.now();
      refresh();
    }
  }, [serverNow, detail, refresh]);

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <Link href="/" className="text-sm text-blue-700 hover:underline">
          ← Back to auctions
        </Link>
        <span className="flex items-center gap-1.5 text-xs text-slate-500">
          <span className={`h-2 w-2 rounded-full ${live ? "bg-green-500" : "bg-slate-300"}`} />
          {live ? "Live" : "Connecting..."}
        </span>
      </div>

      {error && !detail && <div className="rounded-md bg-red-50 p-4 text-sm text-red-700">{error}</div>}
      {!detail && !error && <p className="text-slate-500">Loading...</p>}

      {detail && (
        <div className="space-y-5">
          <AuctionHeader rfq={detail.rfq} serverNow={serverNow} />
          <div className="grid gap-5 lg:grid-cols-3">
            <div className="space-y-5 lg:col-span-2">
              <RankingBoard ranking={detail.ranking} />
              <div className="rounded-lg border border-dashed border-slate-300 p-4 text-center text-sm text-slate-500">
                The bid form goes here (Step 16).
              </div>
              <BidsTable bids={detail.bids} />
            </div>
            <ActivityLog activity={detail.activity} />
          </div>
        </div>
      )}
    </div>
  );
}
