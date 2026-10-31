"use client";

import { FormEvent, ReactNode, useRef, useState } from "react";
import { ApiError, placeBid } from "@/lib/api";
import { formatDateTime, formatMoney } from "@/lib/format";
import type { BidResult, RankingEntry, RFQ } from "@/lib/types";

const MONEY = /^\d{1,10}(\.\d{1,2})?$/;
const inputCls =
  "w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:border-slate-900 focus:outline-none";

function Field({ label, error, children }: { label: string; error?: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-slate-600">{label}</span>
      {children}
      {error && <span className="mt-1 block text-xs text-red-600">{error}</span>}
    </label>
  );
}

const normalise = (s: string) => s.trim().replace(/\s+/g, " ").toLowerCase();

export default function BidForm({
  rfq,
  ranking,
  onPlaced,
}: {
  rfq: RFQ;
  ranking: RankingEntry[];
  onPlaced: () => void;
}) {
  const [f, setF] = useState({
    carrier: "",
    freight: "",
    origin: "",
    destination: "",
    transit: "",
    validity: "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [result, setResult] = useState<BidResult | null>(null);
  const [submitting, setSubmitting] = useState(false);
  // Same key for retries of the same bid, so a double-click can't bid twice
  const keyRef = useRef<string | null>(null);

  const set = (key: keyof typeof f) => (e: { target: { value: string } }) => {
    keyRef.current = null; // the bid changed, so it's a new bid
    setF((p) => ({ ...p, [key]: e.target.value }));
  };

  if (rfq.status !== "ACTIVE") {
    const msg =
      rfq.status === "SCHEDULED"
        ? `Bidding opens at ${formatDateTime(rfq.bid_start)}.`
        : "Bidding has ended for this auction.";
    return (
      <div className="rounded-lg bg-white p-5 text-center text-sm text-slate-600 ring-1 ring-slate-200">{msg}</div>
    );
  }

  const num = (s: string) => (MONEY.test(s) ? Number(s) : 0);
  const total = num(f.freight) + num(f.origin) + num(f.destination);
  const myBest = ranking.find((r) => normalise(r.supplier) === normalise(f.carrier));

  function validate() {
    const e: Record<string, string> = {};
    if (f.carrier.trim().length < 2) e.carrier = "Enter the carrier name";
    for (const [key, label] of [
      ["freight", "freight"],
      ["origin", "origin"],
      ["destination", "destination"],
    ] as const) {
      if (!MONEY.test(f[key])) e[key] = `Enter ${label} charges (0 or more, up to 2 decimals)`;
    }
    if (!e.freight && !e.origin && !e.destination) {
      if (total <= 0) e.freight = "The total must be greater than zero";
      else if (myBest && total >= Number(myBest.bid.total))
        e.freight = `Total must be lower than your current best (${formatMoney(myBest.bid.total)})`;
    }
    for (const key of ["transit", "validity"] as const) {
      const v = Number(f[key]);
      if (!Number.isInteger(v) || v < 1 || v > 365) e[key] = "Enter whole days, 1 to 365";
    }
    return e;
  }

  async function onSubmit(ev: FormEvent) {
    ev.preventDefault();
    setFormError(null);
    setResult(null);
    const found = validate();
    setErrors(found);
    if (Object.keys(found).length > 0) return;

    if (!keyRef.current) keyRef.current = crypto.randomUUID();
    setSubmitting(true);
    try {
      const res = await placeBid(rfq.id, {
        carrier_name: f.carrier.trim(),
        freight_charges: Number(f.freight),
        origin_charges: Number(f.origin),
        destination_charges: Number(f.destination),
        transit_days: Number(f.transit),
        quote_validity_days: Number(f.validity),
        idempotency_key: keyRef.current,
      });
      setResult(res);
      keyRef.current = null;
      setF((p) => ({ ...p, freight: "", origin: "", destination: "" }));
      onPlaced();
    } catch (e) {
      if (e instanceof ApiError) {
        const map: Record<string, string> = {
          carrier_name: "carrier",
          freight_charges: "freight",
          origin_charges: "origin",
          destination_charges: "destination",
          transit_days: "transit",
          quote_validity_days: "validity",
        };
        const fieldErrors: Record<string, string> = {};
        for (const d of e.details) if (map[d.field]) fieldErrors[map[d.field]] = d.message;
        setErrors(fieldErrors);
        setFormError(Object.keys(fieldErrors).length ? "Please fix the highlighted fields." : e.message);
        if (e.code !== "NETWORK") keyRef.current = null; // a real rejection, so the next try is a new bid
      } else {
        setFormError("Something went wrong");
      }
    } finally {
      setSubmitting(false);
    }
  }

  const addedMin = result ? Math.round((new Date(result.new_close).getTime() - new Date(result.previous_close).getTime()) / 60000) : 0;

  return (
    <form onSubmit={onSubmit} noValidate className="rounded-lg bg-white ring-1 ring-slate-200">
      <h2 className="border-b border-slate-100 px-5 py-3 font-semibold">Place a bid</h2>
      <div className="space-y-4 p-5">
        {formError && <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">{formError}</div>}
        {result && (
          <div className="rounded-md bg-green-50 p-3 text-sm text-green-800">
            <strong>Bid accepted. {result.bid.supplier} is now L{result.rank}.</strong>
            <div className="mt-1">
              {result.extended
                ? `The auction was extended by ${addedMin} min, to ${formatDateTime(result.new_close)}.`
                : "The auction was not extended."}
            </div>
            <div className="text-xs text-green-700">{result.reason}</div>
          </div>
        )}

        <Field label="Carrier name" error={errors.carrier}>
          <input className={inputCls} value={f.carrier} onChange={set("carrier")} placeholder="e.g. Alpha Logistics" />
        </Field>

        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="Freight charges" error={errors.freight}>
            <input inputMode="decimal" className={inputCls} value={f.freight} onChange={set("freight")} placeholder="0.00" />
          </Field>
          <Field label="Origin charges" error={errors.origin}>
            <input inputMode="decimal" className={inputCls} value={f.origin} onChange={set("origin")} placeholder="0.00" />
          </Field>
          <Field label="Destination charges" error={errors.destination}>
            <input inputMode="decimal" className={inputCls} value={f.destination} onChange={set("destination")} placeholder="0.00" />
          </Field>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Transit time (days)" error={errors.transit}>
            <input inputMode="numeric" className={inputCls} value={f.transit} onChange={set("transit")} />
          </Field>
          <Field label="Quote validity (days)" error={errors.validity}>
            <input inputMode="numeric" className={inputCls} value={f.validity} onChange={set("validity")} />
          </Field>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 rounded-md bg-slate-50 p-3">
          <div>
            <div className="text-xs uppercase text-slate-500">Your total</div>
            <div className="text-2xl font-bold tabular-nums">{formatMoney(String(total))}</div>
            {myBest && (
              <div className="text-xs text-slate-500">Your current best: {formatMoney(myBest.bid.total)}</div>
            )}
          </div>
          <button
            type="submit"
            disabled={submitting}
            className="rounded-md bg-slate-900 px-5 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
          >
            {submitting ? "Submitting..." : "Submit bid"}
          </button>
        </div>
      </div>
    </form>
  );
}
