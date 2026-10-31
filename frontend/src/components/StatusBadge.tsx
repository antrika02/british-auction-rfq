import type { AuctionStatus } from "@/lib/types";

const STYLES: Record<AuctionStatus, { label: string; cls: string }> = {
  SCHEDULED: { label: "Scheduled", cls: "bg-blue-100 text-blue-800" },
  ACTIVE: { label: "Active", cls: "bg-green-100 text-green-800" },
  CLOSED: { label: "Closed", cls: "bg-slate-200 text-slate-700" },
  FORCE_CLOSED: { label: "Force closed", cls: "bg-red-100 text-red-800" },
};

export default function StatusBadge({ status }: { status: AuctionStatus }) {
  const s = STYLES[status];
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${s.cls}`}>
      {s.label}
    </span>
  );
}
