"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, ReactNode, useEffect, useState } from "react";
import { ApiError, createRfq } from "@/lib/api";
import type { TriggerType } from "@/lib/types";

const pad = (n: number) => String(n).padStart(2, "0");
// "2026-10-31T22:30" in the browser's own timezone, the format <input type="datetime-local"> wants
const toDateTimeInput = (d: Date) =>
  `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
const toDateInput = (d: Date) =>
  `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

const TRIGGERS: { value: TriggerType; label: string; help: string }[] = [
  {
    value: "BID_RECEIVED",
    label: "Any bid",
    help: "Extend when any bid arrives in the trigger window.",
  },
  {
    value: "ANY_RANK_CHANGE",
    label: "Any rank change",
    help: "Extend when any supplier's position changes in the trigger window.",
  },
  {
    value: "L1_CHANGE",
    label: "Lowest bidder (L1) change",
    help: "Extend only when the lowest bidder changes in the trigger window.",
  },
];

function Field({
  label,
  hint,
  error,
  children,
}: {
  label: string;
  hint?: string;
  error?: string;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium">{label}</span>
      {children}
      {hint && !error && <span className="mt-1 block text-xs text-slate-500">{hint}</span>}
      {error && <span className="mt-1 block text-xs text-red-600">{error}</span>}
    </label>
  );
}

const inputCls =
  "w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:border-slate-900 focus:outline-none";

export default function NewRfqPage() {
  const router = useRouter();
  const [f, setF] = useState({
    name: "",
    bidStart: "",
    bidClose: "",
    forcedClose: "",
    pickup: "",
    trigger: "L1_CHANGE" as TriggerType,
    x: "10",
    y: "5",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Fill sensible default times once the page is open in the browser
  useEffect(() => {
    const now = new Date();
    const hours = (h: number) => new Date(now.getTime() + h * 3600_000);
    setF((p) => ({
      ...p,
      bidStart: toDateTimeInput(now),
      bidClose: toDateTimeInput(hours(1)),
      forcedClose: toDateTimeInput(hours(2)),
      pickup: toDateInput(new Date(now.getTime() + 3 * 86400_000)),
    }));
  }, []);

  const set = (key: keyof typeof f) => (e: { target: { value: string } }) =>
    setF((p) => ({ ...p, [key]: e.target.value }));

  function validate(): Record<string, string> {
    const e: Record<string, string> = {};
    const start = new Date(f.bidStart).getTime();
    const close = new Date(f.bidClose).getTime();
    const forced = new Date(f.forcedClose).getTime();
    const x = Number(f.x);
    const y = Number(f.y);

    if (f.name.trim().length < 3) e.name = "Enter at least 3 characters";
    if (!f.bidStart || isNaN(start)) e.bidStart = "Choose a start time";
    if (!f.bidClose || isNaN(close)) e.bidClose = "Choose a close time";
    if (!f.forcedClose || isNaN(forced)) e.forcedClose = "Choose a forced close time";
    if (!f.pickup) e.pickup = "Choose a pickup / service date";
    if (!e.bidStart && !e.bidClose && close <= start)
      e.bidClose = "Bid close time must be later than bid start time";
    if (!e.bidClose && !e.forcedClose && forced <= close)
      e.forcedClose = "Forced bid close time must be later than bid close time";
    if (!e.bidClose && close <= Date.now()) e.bidClose = "Bid close time must be in the future";
    if (!Number.isInteger(x) || x < 1 || x > 1440) e.x = "Enter a whole number from 1 to 1440";
    if (!Number.isInteger(y) || y < 1 || y > 1440) e.y = "Enter a whole number from 1 to 1440";
    return e;
  }

  async function onSubmit(ev: FormEvent) {
    ev.preventDefault();
    setFormError(null);
    const found = validate();
    setErrors(found);
    if (Object.keys(found).length > 0) return;

    setSubmitting(true);
    try {
      await createRfq({
        name: f.name.trim(),
        bid_start: new Date(f.bidStart).toISOString(),
        bid_close: new Date(f.bidClose).toISOString(),
        forced_close: new Date(f.forcedClose).toISOString(),
        pickup_date: f.pickup,
        trigger_type: f.trigger,
        trigger_window_minutes: Number(f.x),
        extension_minutes: Number(f.y),
      });
      router.push("/"); // Step 15 will send you to the new auction's page instead
    } catch (e) {
      if (e instanceof ApiError) {
        // Show backend messages under the matching field when possible
        const map: Record<string, string> = {
          name: "name",
          bid_start: "bidStart",
          bid_close: "bidClose",
          forced_close: "forcedClose",
          pickup_date: "pickup",
          trigger_window_minutes: "x",
          extension_minutes: "y",
        };
        const fieldErrors: Record<string, string> = {};
        for (const d of e.details) {
          const key = map[d.field];
          if (key) fieldErrors[key] = d.message;
        }
        setErrors(fieldErrors);
        setFormError(Object.keys(fieldErrors).length ? "Please fix the highlighted fields." : e.message);
      } else {
        setFormError("Something went wrong");
      }
    } finally {
      setSubmitting(false);
    }
  }

  // A live explanation of what the settings mean for this auction
  const closeMs = new Date(f.bidClose).getTime();
  const xNum = Number(f.x);
  const showPreview = !isNaN(closeMs) && Number.isInteger(xNum) && xNum >= 1;
  const windowOpens = showPreview ? new Date(closeMs - xNum * 60_000) : null;
  const trigger = TRIGGERS.find((t) => t.value === f.trigger)!;

  return (
    <div className="mx-auto max-w-2xl">
      <Link href="/" className="text-sm text-blue-700 hover:underline">
        ← Back to auctions
      </Link>
      <h1 className="mb-4 mt-2 text-2xl font-semibold">Create RFQ</h1>

      <form onSubmit={onSubmit} noValidate className="space-y-5 rounded-lg bg-white p-6 ring-1 ring-slate-200">
        {formError && <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">{formError}</div>}

        <Field label="RFQ name" error={errors.name}>
          <input className={inputCls} value={f.name} onChange={set("name")} placeholder="e.g. Delhi to Mumbai freight" />
        </Field>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Bid start time" error={errors.bidStart}>
            <input type="datetime-local" className={inputCls} value={f.bidStart} onChange={set("bidStart")} />
          </Field>
          <Field label="Pickup / service date" error={errors.pickup}>
            <input type="date" className={inputCls} value={f.pickup} onChange={set("pickup")} />
          </Field>
          <Field label="Bid close time" error={errors.bidClose}>
            <input type="datetime-local" className={inputCls} value={f.bidClose} onChange={set("bidClose")} />
          </Field>
          <Field
            label="Forced bid close time"
            error={errors.forcedClose}
            hint="The hard stop. The auction can never run past this."
          >
            <input type="datetime-local" className={inputCls} value={f.forcedClose} onChange={set("forcedClose")} />
          </Field>
        </div>

        <fieldset className="space-y-4 rounded-md bg-slate-50 p-4">
          <legend className="px-1 text-sm font-semibold">British auction settings</legend>

          <Field label="Extension trigger" hint={trigger.help}>
            <select className={inputCls} value={f.trigger} onChange={set("trigger")}>
              {TRIGGERS.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </Field>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field
              label="Trigger window X (minutes)"
              error={errors.x}
              hint="Watch for activity in the last X minutes before close."
            >
              <input type="number" min={1} className={inputCls} value={f.x} onChange={set("x")} />
            </Field>
            <Field
              label="Extension duration Y (minutes)"
              error={errors.y}
              hint="How many minutes to add each time it triggers."
            >
              <input type="number" min={1} className={inputCls} value={f.y} onChange={set("y")} />
            </Field>
          </div>

          {windowOpens && (
            <p className="text-xs text-slate-600">
              Extensions can happen from{" "}
              <strong>{windowOpens.toLocaleTimeString("en-IN", { timeStyle: "short" })}</strong> until the close
              time. Each trigger adds {f.y || "Y"} min, but never past the forced close time.
            </p>
          )}
        </fieldset>

        <div className="flex justify-end gap-2">
          <Link href="/" className="rounded-md px-4 py-2 text-sm ring-1 ring-slate-300 hover:bg-slate-100">
            Cancel
          </Link>
          <button
            type="submit"
            disabled={submitting}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
          >
            {submitting ? "Creating..." : "Create RFQ"}
          </button>
        </div>
      </form>
    </div>
  );
}
