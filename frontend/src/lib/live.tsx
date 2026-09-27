/** One WebSocket per session: live prices, order/bot events and notifications. Reconnects with backoff. */
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { refreshSession, tokens, wsUrl } from "../api/client";
import { useAuth } from "./auth";
import { useToast } from "./toast";

export interface Tick { symbol: string; price: number; change: number; change_pct: number }
type Listener = (msg: { type: string; data?: unknown }) => void;
interface LiveState {
  prices: Record<string, Tick>; connected: boolean; killSwitch: boolean;
  subscribe(fn: Listener): () => void;
}
const Ctx = createContext<LiveState>({ prices: {}, connected: false, killSwitch: false, subscribe: () => () => {} });

export function LiveProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const toast = useToast();
  const [prices, setPrices] = useState<Record<string, Tick>>({});
  const [connected, setConnected] = useState(false);
  const [killSwitch, setKillSwitch] = useState(false);
  const listeners = useRef(new Set<Listener>());

  useEffect(() => {
    if (!user) return;
    let ws: WebSocket | null = null;
    let stopped = false;
    let attempt = 0;
    let timer: ReturnType<typeof setTimeout>;
    let ping: ReturnType<typeof setInterval>;

    const connect = () => {
      ws = new WebSocket(wsUrl());
      ws.onopen = () => { attempt = 0; setConnected(true); ping = setInterval(() => ws?.readyState === 1 && ws.send("ping"), 25000); };
      ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data);
        if (msg.type === "ticks") {
          setPrices((prev) => {
            const next = { ...prev };
            for (const t of msg.data as Tick[]) next[t.symbol] = t;
            return next;
          });
        } else if (msg.type === "notification") {
          const d = msg.data as { title: string; body: string; kind: string };
          if (!(d.kind === "ORDER_FILLED" && d.body.includes("by you"))) toast(d.title, d.kind === "BOT_ERROR" || d.kind === "ORDER_REJECTED" ? "error" : "info", d.body);
        } else if (msg.type === "kill_switch") {
          setKillSwitch(!!(msg.data as { active: boolean }).active);
        }
        listeners.current.forEach((fn) => fn(msg));
      };
      ws.onclose = async (ev) => {
        setConnected(false);
        clearInterval(ping);
        if (stopped) return;
        if (ev.code === 4401) await refreshSession();
        attempt += 1;
        timer = setTimeout(() => tokens.access && connect(), Math.min(15000, 500 * 2 ** attempt));
      };
    };
    connect();
    return () => { stopped = true; clearTimeout(timer); clearInterval(ping); ws?.close(); };
  }, [user, toast]);

  const subscribe = (fn: Listener) => { listeners.current.add(fn); return () => { listeners.current.delete(fn); }; };
  return <Ctx.Provider value={{ prices, connected, killSwitch, subscribe }}>{children}</Ctx.Provider>;
}

export const useLive = () => useContext(Ctx);

/** Re-run `fn` whenever a live event of one of `types` arrives (throttled). */
export function useLiveRefresh(types: string[], fn: () => void, throttleMs = 1500) {
  const { subscribe } = useLive();
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const key = types.join(",");
  useEffect(() => {
    let last = 0;
    let t: ReturnType<typeof setTimeout> | undefined;
    const unsub = subscribe((m) => {
      if (!key.split(",").includes(m.type)) return;
      const wait = Math.max(0, throttleMs - (Date.now() - last));
      clearTimeout(t);
      t = setTimeout(() => { last = Date.now(); fnRef.current(); }, wait);
    });
    return () => { unsub(); clearTimeout(t); };
  }, [subscribe, key, throttleMs]);
}
