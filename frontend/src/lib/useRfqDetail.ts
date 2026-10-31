"use client";
import { useCallback, useEffect, useState } from "react";
import { getRfq, WS_URL } from "./api";
import type { RFQDetail } from "./types";

export function useRfqDetail(id: string) {
  const [detail, setDetail] = useState<RFQDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [skew, setSkew] = useState(0); // server clock minus browser clock
  const [live, setLive] = useState(false);

  const apply = useCallback((d: RFQDetail) => {
    setDetail(d);
    setSkew(new Date(d.server_time).getTime() - Date.now());
    setError(null);
  }, []);

  const refresh = useCallback(async () => {
    try {
      apply(await getRfq(id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    }
  }, [id, apply]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let timer: ReturnType<typeof setTimeout>;
    let stopped = false;
    const connect = () => {
      ws = new WebSocket(`${WS_URL}/ws/rfqs/${id}`);
      ws.onopen = () => {
        setLive(true);
        refresh(); // catch up on anything missed while disconnected
      };
      ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data);
        if (msg.type === "bid_placed") apply(msg.detail as RFQDetail);
      };
      ws.onclose = () => {
        setLive(false);
        if (!stopped) timer = setTimeout(connect, 2000);
      };
    };
    connect();
    return () => {
      stopped = true;
      clearTimeout(timer);
      ws?.close();
    };
  }, [id, apply, refresh]);

  return { detail, error, skew, live, refresh };
}
