import type { AuctionStatus, BidResult, RFQ, RFQDetail, RFQPage, TriggerType } from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";
export const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8001";

export class ApiError extends Error {
  code: string;
  details: { field: string; message: string }[];
  constructor(message: string, code = "ERROR", details: { field: string; message: string }[] = []) {
    super(message);
    this.code = code;
    this.details = details;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      cache: "no-store",
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError("Cannot reach the server. Is the backend running?", "NETWORK");
  }
  if (!res.ok) {
    let body: { error?: { code?: string; message?: string; details?: ApiError["details"] } } = {};
    try {
      body = await res.json();
    } catch {}
    throw new ApiError(
      body.error?.message ?? `Request failed (${res.status})`,
      body.error?.code,
      body.error?.details,
    );
  }
  return res.json() as Promise<T>;
}

export function listRfqs(p: { status?: AuctionStatus; q?: string; limit: number; offset: number }) {
  const qs = new URLSearchParams({ limit: String(p.limit), offset: String(p.offset) });
  if (p.status) qs.set("status", p.status);
  if (p.q) qs.set("q", p.q);
  return request<RFQPage>(`/api/rfqs?${qs}`);
}

export const getRfq = (id: number | string) => request<RFQDetail>(`/api/rfqs/${id}`);

export interface RFQInput {
  name: string;
  bid_start: string;
  bid_close: string;
  forced_close: string;
  pickup_date: string;
  trigger_type: TriggerType;
  trigger_window_minutes: number;
  extension_minutes: number;
}
export const createRfq = (data: RFQInput) =>
  request<RFQ>("/api/rfqs", { method: "POST", body: JSON.stringify(data) });

export interface BidInput {
  carrier_name: string;
  freight_charges: number;
  origin_charges: number;
  destination_charges: number;
  transit_days: number;
  quote_validity_days: number;
  idempotency_key?: string;
}
export const placeBid = (rfqId: number | string, data: BidInput) =>
  request<BidResult>(`/api/rfqs/${rfqId}/bids`, { method: "POST", body: JSON.stringify(data) });
