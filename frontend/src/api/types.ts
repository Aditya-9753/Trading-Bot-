export type Role = "USER" | "ADMIN" | "SUPER_ADMIN";
export interface User { id: number; email: string; full_name: string; role: Role; created_at: string }
export interface TokenResponse { access_token: string; refresh_token: string; expires_in: number; user: User }

export interface Instrument {
  symbol: string; name: string; exchange: string; series?: string; sector: string;
  asset_type?: "EQUITY" | "INDEX" | "CRYPTO" | string;
  last_price: number; prev_close: number;
  change: number; change_pct: number; data_source: string; simulated: boolean; is_active: boolean; updated_at: string;
  high_52w?: number; low_52w?: number; avg_volume_20?: number;
}
export interface Candle { t: string; o: number; h: number; l: number; c: number; v: number }
export interface ChartData {
  symbol: string; candles: Candle[]; ema20: (number | null)[]; ema50: (number | null)[]; rsi: (number | null)[];
  macd: (number | null)[]; macd_signal: (number | null)[]; macd_hist: (number | null)[];
}
export interface Watchlist { id: number; name: string; items: Instrument[] }

export type Side = "BUY" | "SELL";
export type OrderType = "MARKET" | "LIMIT" | "STOP";
export interface Order {
  id: number; symbol: string; side: Side; order_type: OrderType; quantity: number; limit_price: number | null;
  stop_price: number | null; stop_loss: number | null; target: number | null;
  status: "OPEN" | "FILLED" | "CANCELLED" | "REJECTED"; filled_qty: number; avg_fill_price: number | null;
  fees: number; reject_reason: string | null; source: "MANUAL" | "BOT" | "SYSTEM"; bot_id: number | null;
  created_at: string; updated_at: string;
}
export interface Fill {
  id: number; order_id: number; symbol: string; side: Side; quantity: number; price: number; fees: number;
  realized_pnl: number; bot_id: number | null; created_at: string;
}
export interface Paged<T> { total: number; items: T[] }

export interface Position {
  symbol: string; name: string; quantity: number; avg_price: number; last_price: number; market_value: number;
  unrealized_pnl: number; unrealized_pct: number; day_change: number; stop_loss: number | null; target: number | null;
  bot_quantity: number; opened_at: string;
}
export interface PortfolioSummary {
  cash: number; invested: number; market_value: number; equity: number; starting_cash: number; total_pnl: number;
  total_pnl_pct: number; realized_pnl: number; unrealized_pnl: number; day_pnl: number; day_pnl_pct: number;
  fees_paid: number; trades_today: number; drawdown_pct: number;
}
export interface Portfolio extends PortfolioSummary { positions: Position[] }
export interface Analytics {
  closed_trades: number; wins: number; losses: number; win_rate: number | null; avg_win: number | null;
  avg_loss: number | null; profit_factor: number | null; largest_win: number | null; largest_loss: number | null;
  realized_pnl: number; fees_paid: number; max_drawdown_pct: number;
  by_symbol: { symbol: string; pnl: number }[]; by_source: { source: string; pnl: number }[];
}
export interface RiskLimits {
  daily_loss_limit_pct: number; max_position_pct: number; max_open_positions: number; max_daily_trades: number;
  short_selling: boolean;
}
export interface EquityPoint { t: string; equity: number; cash: number }

export interface TunableParam { name: string; min: number; max: number; type: "float" | "int"; label: string; help: string; default: number }
export interface StrategyMeta {
  versions: string[]; default_version: string; version: string; tunable: TunableParam[]; components: string[];
  weights: Record<string, Record<string, number>>; notes: string;
}
export interface SignalLatest {
  t: string; S: number | null; regime: string; confidence: number | null; atr: number | null; vol_ratio: number | null;
  scores: Record<string, number | null>; contributions: Record<string, number | null>;
}
export interface Evaluation {
  symbol: string; algorithm_version: string; components: string[]; weights: Record<string, Record<string, number>>;
  series: { t: string; S: number | null; regime: string; close: number | null }[]; latest: SignalLatest;
  thresholds: { entry: number; confirm: number; long_exit: number };
  decision: { action: string; S: number; regime: string; confidence: number };
}

export type Metrics = Record<string, number | null>;
export interface BacktestTrade {
  side: string; entry_time: string; entry_price: number; exit_time: string | null; exit_price: number | null; qty: number;
  pnl: number | null; exit_reason: string; regime: string; score: number; policy: string;
}
export interface Backtest {
  id: number; symbol: string; bot_id: number | null; algorithm_version: string; params: Record<string, number>;
  initial_capital: number; status: "DONE" | "FAILED"; bars: number; start: string | null; end: string | null;
  metrics: Metrics | null; error: string | null; created_at: string; has_walk_forward: boolean; has_robustness: boolean;
  equity_curve?: { t: string; v: number }[]; benchmark_curve?: { t: string; v: number }[] | null;
  trades?: BacktestTrade[]; walk_forward?: Record<string, number | string | null>[] | null;
  robustness?: Record<string, number | string | null>[] | null;
}

export type BotStatus = "DRAFT" | "BACKTESTED" | "RUNNING" | "PAUSED" | "STOPPED" | "ERROR";
export interface BotDecision {
  action: string; S: number; regime: string; confidence: number; atr: number; vol_ratio: number;
  contributions: Record<string, number>; time: string; algorithm_version: string;
}
export interface Bot {
  id: number; name: string; symbol: string; algorithm_version: string; params: Record<string, number>;
  capital_allocation: number; status: BotStatus; position_qty: number; entry_price: number | null;
  stop_price: number | null; target_price: number | null; last_price: number; unrealized_pnl: number;
  realized_pnl: number; trade_count: number; last_decision: BotDecision | null;
  last_evaluated_at: string | null; last_backtest_id: number | null; backtest_current: boolean;
  error_message: string | null; created_at: string; owner?: string;
}
export interface BotLog { id: number; ts: string; level: "INFO" | "WARN" | "ERROR"; event: string; message: string; data: Record<string, unknown> | null }

export interface Alert {
  id: number; symbol: string; condition: "ABOVE" | "BELOW"; price: number; note: string; is_active: boolean;
  triggered_at: string | null; created_at: string; last_price: number;
}
export interface Notification { id: number; kind: string; title: string; body: string; is_read: boolean; created_at: string }

export interface Dashboard {
  portfolio: PortfolioSummary; positions: Position[]; recent_orders: Order[];
  bots: { total: number; running: number; error: number; items: Bot[] }; movers: Instrument[];
  checklist: { key: string; label: string; done: boolean }[]; unread_notifications: number; kill_switch: boolean;
}
export interface MarketStatus {
  practice_market_open: boolean; nse_session_open: boolean; simulated: boolean; kill_switch: boolean;
  ticks_per_bar: number; tick_seconds: number; note: string;
}
export interface AdminStats {
  users: number; active_users: number; bots_running: number; bots_error: number; orders_today: number;
  trades_today: number; open_orders: number; instruments: number;
  kill_switch: { active: boolean; reason?: string; by?: string; at?: string };
}
export interface AdminUser {
  id: number; email: string; full_name: string; role: Role; is_active: boolean; created_at: string;
  last_login_at: string | null; equity: number | null; bots: number;
}
export interface AuditEntry { id: number; user: string | null; action: string; target: string; detail: unknown; ip: string; created_at: string }
