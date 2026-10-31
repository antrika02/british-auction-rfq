import type { Activity } from "@/lib/types";

const DOT: Record<string, string> = {
  RFQ_CREATED: "bg-blue-500",
  BID_PLACED: "bg-slate-400",
  EXTENSION: "bg-amber-500",
  EXTENSION_BLOCKED: "bg-red-500",
};

export default function ActivityLog({ activity }: { activity: Activity[] }) {
  return (
    <div className="rounded-lg bg-white ring-1 ring-slate-200">
      <h2 className="border-b border-slate-100 px-5 py-3 font-semibold">Activity log</h2>
      <ul className="max-h-[32rem] space-y-4 overflow-y-auto px-5 py-4">
        {activity.map((a) => (
          <li key={a.id} className="flex gap-3">
            <span className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${DOT[a.kind] ?? "bg-slate-400"}`} />
            <div>
              <div className={`text-sm ${a.kind === "EXTENSION" ? "font-medium" : ""}`}>{a.message}</div>
              <div className="text-xs text-slate-500">
                {new Date(a.created_at).toLocaleTimeString("en-IN", { timeStyle: "medium" })}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
