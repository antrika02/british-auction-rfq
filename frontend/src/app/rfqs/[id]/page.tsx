import { Suspense } from "react";
import AuctionView from "@/components/AuctionView";

export default function AuctionPage() {
  return (
    <Suspense fallback={<p className="text-slate-500">Loading...</p>}>
      <AuctionView />
    </Suspense>
  );
}
