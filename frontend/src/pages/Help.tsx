import { Link } from "react-router-dom";
import SignalGauge from "../components/SignalGauge";
import { Panel } from "../components/ui";

export default function Help() {
  return (
    <>
      <div className="page-head"><div><h1>How it works</h1><p>What TradeBot is, what it isn't, and how the algorithm decides.</p></div></div>
      <div className="grid g-main-side">
        <Panel className="help-body">
          <h2 style={{ marginTop: 0 }}>This is a practice platform</h2>
          <p>All money is virtual. Live prices come from a simulator, not the exchange, and move every second. History is simulated too unless an admin has imported NSE bhav copies. Nothing you do here places a real order.</p>
          <p>Each practice bar compresses one trading session into about 30 seconds, so bots act many times an hour instead of once a day.</p>

          <h2>The Hybrid algorithm, v1.2</h2>
          <p>On every closed bar the algorithm works out four component scores between −1 and +1:</p>
          <ul>
            <li><b>Trend</b>: how far the fast average sits above or below the slow one, relative to normal price movement.</li>
            <li><b>Momentum</b>: the 20-bar return, scaled so it rarely saturates.</li>
            <li><b>Reversion</b>: RSI and distance from the 20-bar mean, combined. It bets on a snap-back.</li>
            <li><b>Volume</b>: whether unusual volume confirms the move.</li>
          </ul>
          <p>It then decides the market regime. A trending market weights trend and momentum heavily; a sideways market leans on reversion. When volatility is unusually high, it doesn't open new trades at all. The weighted sum is the signal score S.</p>

          <h2>When a bot trades</h2>
          <ul>
            <li>It buys when S reaches the entry level (+0.55 by default) and the previous bar was already above the confirmation level.</li>
            <li>The size risks about 1% of the bot's capital between entry and stop-loss, scaled down when conviction is lower or risk is higher.</li>
            <li>The stop-loss starts 2 × ATR below entry and only ever moves up as the price rises. The target is 2× the risk above entry.</li>
            <li>It sells when the stop or target is hit, or when S falls below the exit level (−0.25).</li>
          </ul>

          <h2>Costs</h2>
          <p>Every fill includes slippage plus approximate Indian delivery charges: STT, exchange fees, SEBI fee, stamp duty and GST. Brokerage is zero. These rates are estimates; check current rates before relying on them.</p>

          <h2>Read backtests with care</h2>
          <p>A good backtest on simulated data proves the machinery works, not that the strategy makes money. Before trusting any strategy, test it on several real NSE stocks, check the walk-forward and robustness tabs, and keep a final stretch of data untouched until the very end.</p>

          <h2>Safety rails</h2>
          <ul>
            <li>Risk limits in <Link to="/settings">Settings</Link> block new buys when crossed. Sells are always allowed.</li>
            <li>A bot must pass a backtest with its current settings before it can start.</li>
            <li>Each evaluation runs in an isolated process with time and memory limits. If it fails, the bot moves to an error state and you're notified.</li>
            <li>An administrator can pause all trading platform-wide.</li>
          </ul>
        </Panel>
        <Panel title="Reading the gauge">
          <SignalGauge value={0.62} entry={0.55} exit={-0.25} action="BUY" size={280} />
          <p className="small" style={{ marginTop: 12 }}>The marigold arc is the buy zone. The pale red arc on the left is where the algorithm would short (disabled here) and the pink band is where longs are closed. The dark marks show the ±entry levels.</p>
        </Panel>
      </div>
    </>
  );
}
