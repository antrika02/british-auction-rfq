export type AuctionStatus = "SCHEDULED" | "ACTIVE" | "CLOSED" | "FORCE_CLOSED";
export type TriggerType = "BID_RECEIVED" | "ANY_RANK_CHANGE" | "L1_CHANGE";

// Money arrives as a string like "1300.00" so no precision is lost
export interface RFQ {
  id: number;
  reference_id: string;
  name: string;
  status: AuctionStatus;
  bid_start: string;
  bid_close: string;
  original_bid_close: string;
  forced_close: string;
  pickup_date: string;
  trigger_type: TriggerType;
  trigger_window_minutes: number;
  extension_minutes: number;
  bid_count: number;
  extension_count: number;
  lowest_bid: string | null;
  created_at: string;
}

export interface RFQPage {
  items: RFQ[];
  total: number;
  limit: number;
  offset: number;
  server_time: string;
}

export interface Bid {
  id: number;
  supplier: string;
  freight_charges: string;
  origin_charges: string;
  destination_charges: string;
  total: string;
  transit_days: number;
  quote_validity_days: number;
  created_at: string;
}

export interface RankingEntry {
  rank: number;
  label: string;
  supplier: string;
  bid: Bid;
  bid_count: number;
}

export interface Activity {
  id: number;
  kind: string;
  message: string;
  details: Record<string, unknown>;
  created_at: string;
}

export interface RFQDetail {
  rfq: RFQ;
  ranking: RankingEntry[];
  bids: Bid[];
  activity: Activity[];
  server_time: string;
}

export interface BidResult {
  bid: Bid;
  duplicate: boolean;
  rank: number;
  extended: boolean;
  previous_close: string;
  new_close: string;
  reason: string;
  rfq: RFQ;
}
