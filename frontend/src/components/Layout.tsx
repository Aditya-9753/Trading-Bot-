import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { get } from "../api/client";
import type { MarketStatus } from "../api/types";
import { isAdmin, useAuth } from "../lib/auth";
import { useLive, useLiveRefresh } from "../lib/live";

function roleLabel(role?: string) {
  if (role === "SUPER_ADMIN") return { icon: "⭐", text: "Super Admin", gold: true };
  if (role === "ADMIN") return { icon: "🛡", text: "Admin", gold: true };
  return { icon: "", text: "Trader", gold: false };
}


export default function Layout() {
  const { user, logout } = useAuth();
  const { connected, killSwitch } = useLive();
  const [open, setOpen] = useState(false);
  const [unread, setUnread] = useState(0);
  const [halted, setHalted] = useState(false);
  const loc = useLocation();

  const loadUnread = () => get<{ unread: number }>("/notifications?unread_only=true&limit=1").then((r) => setUnread(r.unread)).catch(() => undefined);
  useEffect(() => { setOpen(false); }, [loc.pathname]);
  useEffect(() => {
    void loadUnread();
    get<MarketStatus>("/markets/status").then((s) => setHalted(s.kill_switch)).catch(() => undefined);
  }, [loc.pathname]);
  useLiveRefresh(["notification"], loadUnread, 500);
  useEffect(() => { if (killSwitch) setHalted(true); }, [killSwitch]);

  const displayName = user?.full_name || user?.email || "User";
  const userInitial = displayName.charAt(0).toUpperCase();

  return (
    <div className={`shell ${open ? "nav-open" : ""}`}>
      {open && <button className="scrim" aria-label="Close menu" onClick={() => setOpen(false)} />}
      <aside className="sidebar" aria-label="Main navigation">
        <Link to="/" className="brand">
          <div className="brand-icon">
            <svg viewBox="0 0 32 24" fill="none" aria-hidden>
              <path d="M3 21 A13 13 0 0 1 29 21" stroke="url(#brandGrad)" strokeWidth="3.5" strokeLinecap="round" />
              <line x1="16" y1="21" x2="23" y2="10" stroke="#F59E0B" strokeWidth="3" strokeLinecap="round" />
              <circle cx="16" cy="21" r="2.5" fill="#F59E0B" />
              <defs>
                <linearGradient id="brandGrad" x1="3" y1="21" x2="29" y2="21" gradientUnits="userSpaceOnUse">
                  <stop stopColor="#38BDF8" />
                  <stop offset="1" stopColor="#06B6D4" />
                </linearGradient>
              </defs>
            </svg>
          </div>
          <div className="brand-text">
            <span>TradeBot</span>
            <small>QUANT TERMINAL</small>
          </div>
        </Link>
        <nav className="nav">
          <NavLink to="/" end>
            <svg className="nav-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/></svg>
            <span>Dashboard</span>
          </NavLink>
          <NavLink to="/markets">
            <svg className="nav-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/><line x1="3" y1="20" x2="21" y2="20"/></svg>
            <span>Markets</span>
          </NavLink>
          <NavLink to="/watchlists">
            <svg className="nav-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
            <span>Watchlists</span>
          </NavLink>

          <div className="nav-group">Trading</div>
          <NavLink to="/portfolio">
            <svg className="nav-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 12V7H3v10a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-5"/><path d="M16 3H8a2 2 0 0 0-2 2v2h12V5a2 2 0 0 0-2-2z"/><circle cx="16" cy="14" r="1.5"/></svg>
            <span>Portfolio</span>
          </NavLink>
          <NavLink to="/orders">
            <svg className="nav-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
            <span>Orders</span>
          </NavLink>
          <NavLink to="/alerts">
            <svg className="nav-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
            <span>Alerts</span>
            {unread > 0 && <span className="count">{unread}</span>}
          </NavLink>

          <div className="nav-group">Automation</div>
          <NavLink to="/strategy">
            <svg className="nav-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M10 2v7.31L4.1 19.4A2 2 0 0 0 5.8 22h12.4a2 2 0 0 0 1.7-2.6L14 9.31V2"/><line x1="8" y1="2" x2="16" y2="2"/><line x1="7" y1="14" x2="17" y2="14"/></svg>
            <span>Strategy lab</span>
          </NavLink>
          <NavLink to="/backtests">
            <svg className="nav-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
            <span>Backtests</span>
          </NavLink>
          <NavLink to="/bots">
            <svg className="nav-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="11" width="18" height="10" rx="2"/><circle cx="12" cy="5" r="2"/><path d="M12 7v4"/><line x1="8" y1="16" x2="8.01" y2="16"/><line x1="16" y1="16" x2="16.01" y2="16"/></svg>
            <span>Bots</span>
          </NavLink>

          <div className="nav-group">Account</div>
          <NavLink to="/settings">
            <svg className="nav-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
            <span>Settings</span>
          </NavLink>
          <NavLink to="/help">
            <svg className="nav-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
            <span>How it works</span>
          </NavLink>
          {isAdmin(user) && (
            <NavLink to="/admin">
              <svg className="nav-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
              <span>Admin</span>
            </NavLink>
          )}
        </nav>
        <div className="sidebar-foot">
          <div className={`user-profile-badge ${isAdmin(user) ? "user-profile-admin" : ""}`}>
            <div className={`user-avatar ${isAdmin(user) ? "user-avatar-admin" : ""}`}>
              {isAdmin(user) ? (user?.role === "SUPER_ADMIN" ? "⭐" : "🛡") : userInitial}
            </div>
            <div className="user-info">
              <span className="who">{displayName}</span>
              <span className={`user-role ${roleLabel(user?.role).gold ? "user-role-admin" : ""}`}>
                {roleLabel(user?.role).icon} {roleLabel(user?.role).text}
              </span>
            </div>
          </div>
          <button className="logout-btn" onClick={() => void logout()} title="Sign out of account">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
            <span>Log out</span>
          </button>
        </div>
      </aside>
      <div className="main">
        <header className="topbar">
          <button className="btn btn-ghost menu-btn" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
            <span>Menu</span>
          </button>
          <span className="ribbon" title="All money is virtual and all live prices are simulated">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
            Practice money<span className="rb-long">, simulated prices</span>
          </span>
          <span className={`conn ${connected ? "on" : ""}`}>{connected ? "Live feed" : "Connecting…"}</span>
          <span className="spacer" />
          <Link to="/alerts" className="bell" aria-label="Notifications">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
            <span>Notifications</span>
            {unread > 0 && <b>{unread}</b>}
          </Link>
        </header>
        {halted && <div className="killbar" role="alert">Trading is paused by the platform. New buys and bots are blocked; you can still sell.</div>}
        <main className="page"><Outlet /></main>
      </div>
    </div>
  );
}
