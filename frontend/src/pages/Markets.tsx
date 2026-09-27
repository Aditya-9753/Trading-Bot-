import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { Instrument } from "../api/types";
import { ErrorBox, LivePrice, Loading, Panel, SymbolLink } from "../components/ui";
import { useApi } from "../lib/useApi";
import { useLive } from "../lib/live";
import { pct, signedMoney, tone } from "../lib/format";

type AssetTab = "ALL" | "EQUITY" | "INDEX" | "CRYPTO";

export default function Markets() {
  const { data, error, loading, reload } = useApi<Instrument[]>("/markets");
  const { prices } = useLive();
  const [tab, setTab] = useState<AssetTab>("ALL");
  const [q, setQ] = useState("");
  const [sector, setSector] = useState("");
  const [sort, setSort] = useState<"symbol" | "gainers" | "losers" | "price">("symbol");

  const instruments = data ?? [];

  // Filter available sectors based on active tab
  const sectors = useMemo(() => {
    const pool = tab === "ALL" ? instruments : instruments.filter((i) => (i.asset_type || "EQUITY") === tab);
    return [...new Set(pool.map((i) => i.sector).filter(Boolean))].sort();
  }, [instruments, tab]);

  // Counts for tabs
  const counts = useMemo(() => {
    let eq = 0, idx = 0, cry = 0;
    for (const i of instruments) {
      const t = i.asset_type || "EQUITY";
      if (t === "EQUITY") eq++;
      else if (t === "INDEX") idx++;
      else if (t === "CRYPTO") cry++;
    }
    return { all: instruments.length, eq, idx, cry };
  }, [instruments]);

  // Filtered and sorted rows
  const rows = useMemo(() => {
    const ql = q.trim().toLowerCase();
    const filtered = instruments.filter((i) => {
      const type = i.asset_type || "EQUITY";
      if (tab !== "ALL" && type !== tab) return false;
      if (sector && i.sector !== sector) return false;
      if (ql && !i.symbol.toLowerCase().includes(ql) && !i.name.toLowerCase().includes(ql)) return false;
      return true;
    });

    const getPx = (i: Instrument) => prices[i.symbol]?.price ?? i.last_price;
    const getChg = (i: Instrument) => prices[i.symbol]?.change_pct ?? i.change_pct;

    return [...filtered].sort((a, b) => {
      if (sort === "gainers") return getChg(b) - getChg(a);
      if (sort === "losers") return getChg(a) - getChg(b);
      if (sort === "price") return getPx(b) - getPx(a);
      return a.symbol.localeCompare(b.symbol);
    });
  }, [instruments, tab, sector, q, sort, prices]);

  // Top benchmark items for top cards
  const nifty = instruments.find((i) => i.symbol === "NIFTY50");
  const sensex = instruments.find((i) => i.symbol === "SENSEX");
  const bankNifty = instruments.find((i) => i.symbol === "BANKNIFTY");
  const btc = instruments.find((i) => i.symbol === "BTC");

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Markets</h1>
          <p>Real-time practice feeds for Indian Equities (NSE), Benchmark Indices, and Crypto assets in ₹ INR.</p>
        </div>
      </div>

      {/* Top 4 Benchmark and Crypto Cards */}
      <div className="benchmark-ticker-grid">
        {/* NIFTY 50 */}
        <Link to={nifty ? `/markets/${nifty.symbol}` : "#"} className="benchmark-card nifty">
          <div className="benchmark-card-head">
            <div className="benchmark-card-title">
              <span>📊</span> NIFTY 50
            </div>
            <span className="badge-asset index">NSE INDEX</span>
          </div>
          <div className="benchmark-card-sub">National Stock Exchange Benchmark</div>
          <div className="benchmark-card-body">
            <span className="benchmark-card-price">
              {nifty ? <LivePrice symbol={nifty.symbol} fallback={nifty.last_price} showChange={false} /> : "—"}
            </span>
            {nifty && (
              <span className={`num ${tone(prices[nifty.symbol]?.change ?? nifty.change)}`}>
                {pct(prices[nifty.symbol]?.change_pct ?? nifty.change_pct)}
              </span>
            )}
          </div>
        </Link>

        {/* SENSEX */}
        <Link to={sensex ? `/markets/${sensex.symbol}` : "#"} className="benchmark-card sensex">
          <div className="benchmark-card-head">
            <div className="benchmark-card-title">
              <span>🏛️</span> SENSEX
            </div>
            <span className="badge-asset index">BSE INDEX</span>
          </div>
          <div className="benchmark-card-sub">Bombay Stock Exchange 30</div>
          <div className="benchmark-card-body">
            <span className="benchmark-card-price">
              {sensex ? <LivePrice symbol={sensex.symbol} fallback={sensex.last_price} showChange={false} /> : "—"}
            </span>
            {sensex && (
              <span className={`num ${tone(prices[sensex.symbol]?.change ?? sensex.change)}`}>
                {pct(prices[sensex.symbol]?.change_pct ?? sensex.change_pct)}
              </span>
            )}
          </div>
        </Link>

        {/* BANK NIFTY */}
        <Link to={bankNifty ? `/markets/${bankNifty.symbol}` : "#"} className="benchmark-card banknifty">
          <div className="benchmark-card-head">
            <div className="benchmark-card-title">
              <span>🏦</span> BANK NIFTY
            </div>
            <span className="badge-asset index">BANKING</span>
          </div>
          <div className="benchmark-card-sub">Indian Banking Sector Index</div>
          <div className="benchmark-card-body">
            <span className="benchmark-card-price">
              {bankNifty ? <LivePrice symbol={bankNifty.symbol} fallback={bankNifty.last_price} showChange={false} /> : "—"}
            </span>
            {bankNifty && (
              <span className={`num ${tone(prices[bankNifty.symbol]?.change ?? bankNifty.change)}`}>
                {pct(prices[bankNifty.symbol]?.change_pct ?? bankNifty.change_pct)}
              </span>
            )}
          </div>
        </Link>

        {/* BITCOIN */}
        <Link to={btc ? `/markets/${btc.symbol}` : "#"} className="benchmark-card btc">
          <div className="benchmark-card-head">
            <div className="benchmark-card-title">
              <span>₿</span> BITCOIN
            </div>
            <span className="badge-asset crypto">CRYPTO</span>
          </div>
          <div className="benchmark-card-sub">BTC / INR Practice Market</div>
          <div className="benchmark-card-body">
            <span className="benchmark-card-price">
              {btc ? <LivePrice symbol={btc.symbol} fallback={btc.last_price} showChange={false} /> : "—"}
            </span>
            {btc && (
              <span className={`num ${tone(prices[btc.symbol]?.change ?? btc.change)}`}>
                {pct(prices[btc.symbol]?.change_pct ?? btc.change_pct)}
              </span>
            )}
          </div>
        </Link>
      </div>

      <Panel>
        {/* Category Tabs */}
        <div className="market-nav-tabs">
          <button
            type="button"
            className={`market-tab-btn ${tab === "ALL" ? "active" : ""}`}
            onClick={() => { setTab("ALL"); setSector(""); }}
          >
            All Markets <span className="market-tab-count">{counts.all}</span>
          </button>
          <button
            type="button"
            className={`market-tab-btn ${tab === "EQUITY" ? "active" : ""}`}
            onClick={() => { setTab("EQUITY"); setSector(""); }}
          >
            📈 Equities (NSE) <span className="market-tab-count">{counts.eq}</span>
          </button>
          <button
            type="button"
            className={`market-tab-btn ${tab === "INDEX" ? "active index-active" : ""}`}
            onClick={() => { setTab("INDEX"); setSector(""); }}
          >
            📊 Indices (Nifty / Sensex) <span className="market-tab-count">{counts.idx}</span>
          </button>
          <button
            type="button"
            className={`market-tab-btn ${tab === "CRYPTO" ? "active crypto-active" : ""}`}
            onClick={() => { setTab("CRYPTO"); setSector(""); }}
          >
            ₿ Crypto (INR) <span className="market-tab-count">{counts.cry}</span>
          </button>
        </div>

        {/* Search, Filter, Sort Controls */}
        <div className="row" style={{ marginBottom: 14, gap: 10, flexWrap: "wrap" }}>
          <input
            className="search"
            placeholder={
              tab === "EQUITY"
                ? "Search stocks (e.g. Reliance, TCS)..."
                : tab === "INDEX"
                ? "Search indices (e.g. NIFTY, SENSEX)..."
                : tab === "CRYPTO"
                ? "Search crypto (e.g. BTC, ETH, Solana)..."
                : "Search symbol or asset name..."
            }
            value={q}
            onChange={(e) => setQ(e.target.value)}
            aria-label="Search"
            style={{ minWidth: 240, flex: 1 }}
          />
          <select
            value={sector}
            onChange={(e) => setSector(e.target.value)}
            style={{ width: "auto" }}
            aria-label="Sector"
          >
            <option value="">All Sectors ({sectors.length})</option>
            {sectors.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value as any)}
            style={{ width: "auto" }}
            aria-label="Sort"
          >
            <option value="symbol">Sort: Symbol (A-Z)</option>
            <option value="gainers">Sort: Top Gainers (%)</option>
            <option value="losers">Sort: Top Losers (%)</option>
            <option value="price">Sort: Price (High to Low)</option>
          </select>
        </div>

        {loading ? (
          <Loading />
        ) : error ? (
          <ErrorBox message={error} onRetry={reload} />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Instrument</th>
                  <th>Market / Sector</th>
                  <th className="num">Price</th>
                  <th className="num">Today's Change</th>
                  <th className="num">Points</th>
                  <th style={{ textAlign: "right" }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((i) => {
                  const t = prices[i.symbol];
                  const liveChg = t?.change ?? i.change;
                  const liveChgPct = t?.change_pct ?? i.change_pct;
                  const assetType = i.asset_type || "EQUITY";
                  const isIndex = assetType === "INDEX";
                  const isCrypto = assetType === "CRYPTO";

                  return (
                    <tr key={i.symbol}>
                      <td>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <SymbolLink symbol={i.symbol} />
                          <span
                            className={`badge-asset ${
                              isIndex ? "index" : isCrypto ? "crypto" : "equity"
                            }`}
                          >
                            {isIndex ? "INDEX" : isCrypto ? "CRYPTO" : i.exchange || "NSE"}
                          </span>
                        </div>
                        <span className="sub">{i.name}</span>
                      </td>
                      <td>
                        <span className="muted">{i.sector}</span>
                        <div className="table-tag">
                          <span>{i.exchange}</span>
                          <span>•</span>
                          <span>{isIndex ? "Benchmark" : "Tradeable"}</span>
                        </div>
                      </td>
                      <td className="num">
                        <LivePrice symbol={i.symbol} fallback={i.last_price} showChange={false} />
                      </td>
                      <td className={`num ${tone(liveChg)}`}>
                        <b>{pct(liveChgPct)}</b>
                      </td>
                      <td className={`num small ${tone(liveChg)}`}>
                        {signedMoney(liveChg)}
                      </td>
                      <td style={{ textAlign: "right" }}>
                        <Link
                          to={`/markets/${i.symbol}`}
                          className={`btn ${isIndex ? "btn-secondary" : "btn-primary"}`}
                          style={{ padding: "4px 12px", fontSize: "0.8rem" }}
                        >
                          {isIndex ? "View Chart" : "Trade"}
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {!loading && rows.length === 0 && (
          <div style={{ padding: "30px 20px", textAlign: "center" }}>
            <p className="muted" style={{ margin: 0 }}>
              No instruments match your current filter ({q ? `query: "${q}"` : ""} {sector ? `sector: "${sector}"` : ""}).
            </p>
          </div>
        )}

        {/* Educational Note */}
        <div style={{ marginTop: 20, paddingTop: 16, borderTop: "1px solid var(--line)" }} className="small muted">
          <b>Market Guide:</b>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 12, marginTop: 8 }}>
            <div>
              <span className="badge-asset equity" style={{ marginRight: 6 }}>EQUITY</span>
              Trade simulated Indian shares (NSE) with stop-loss, targets, and bot automation.
            </div>
            <div>
              <span className="badge-asset index" style={{ marginRight: 6 }}>INDEX</span>
              Nifty 50, Sensex, and sector indices track market health. Benchmarks are view-only.
            </div>
            <div>
              <span className="badge-asset crypto" style={{ marginRight: 6 }}>CRYPTO</span>
              Bitcoin, Ethereum, Solana, and top crypto assets priced in ₹ INR with full buy/sell support.
            </div>
          </div>
        </div>
      </Panel>
    </>
  );
}
