import { lazy, Suspense, type ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import Layout from "./components/Layout";
import { Loading } from "./components/ui";
import { isAdmin, useAuth } from "./lib/auth";
import { ForgotPassword, Login, Register, ResetPassword } from "./pages/Auth";

const Dashboard = lazy(() => import("./pages/Dashboard"));
const Markets = lazy(() => import("./pages/Markets"));
const StockDetail = lazy(() => import("./pages/StockDetail"));
const Watchlists = lazy(() => import("./pages/Watchlists"));
const Orders = lazy(() => import("./pages/Orders"));
const Portfolio = lazy(() => import("./pages/Portfolio"));
const StrategyLab = lazy(() => import("./pages/StrategyLab"));
const Backtests = lazy(() => import("./pages/Backtests"));
const BacktestDetail = lazy(() => import("./pages/BacktestDetail"));
const Bots = lazy(() => import("./pages/Bots"));
const BotDetail = lazy(() => import("./pages/BotDetail"));
const Alerts = lazy(() => import("./pages/Alerts"));
const Settings = lazy(() => import("./pages/Settings"));
const Help = lazy(() => import("./pages/Help"));
const Admin = lazy(() => import("./pages/Admin"));

function Protected({ children }: { children: ReactNode }) {
  const { user, ready } = useAuth();
  const loc = useLocation();
  if (!ready) return <Loading label="Starting" />;
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  return <>{children}</>;
}

function AdminOnly({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  return isAdmin(user) ? <>{children}</> : <Navigate to="/" replace />;
}

function PublicOnly({ children }: { children: ReactNode }) {
  const { user, ready } = useAuth();
  if (!ready) return <Loading label="Starting" />;
  return user ? <Navigate to="/" replace /> : <>{children}</>;
}

export default function App() {
  return (
    <Suspense fallback={<Loading />}>
      <Routes>
        <Route path="/login" element={<PublicOnly><Login /></PublicOnly>} />
        <Route path="/register" element={<PublicOnly><Register /></PublicOnly>} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route element={<Protected><Layout /></Protected>}>
          <Route index element={<Dashboard />} />
          <Route path="markets" element={<Markets />} />
          <Route path="markets/:symbol" element={<StockDetail />} />
          <Route path="watchlists" element={<Watchlists />} />
          <Route path="orders" element={<Orders />} />
          <Route path="portfolio" element={<Portfolio />} />
          <Route path="strategy" element={<StrategyLab />} />
          <Route path="backtests" element={<Backtests />} />
          <Route path="backtests/:id" element={<BacktestDetail />} />
          <Route path="bots" element={<Bots />} />
          <Route path="bots/:id" element={<BotDetail />} />
          <Route path="alerts" element={<Alerts />} />
          <Route path="settings" element={<Settings />} />
          <Route path="help" element={<Help />} />
          <Route path="admin" element={<AdminOnly><Admin /></AdminOnly>} />
          <Route path="*" element={<div className="empty"><p className="empty-title">Page not found</p><p className="empty-body">The link may be old. Use the menu to find your way.</p></div>} />
        </Route>
      </Routes>
    </Suspense>
  );
}
