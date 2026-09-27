import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  get,
  post,
  refreshSession,
  setLogoutHandler,
  tokens,
} from "../api/client";

import type { TokenResponse, User } from "../api/types";

/* =========================================================
   AUTH TYPES
========================================================= */

interface AuthState {
  user: User | null;
  ready: boolean;

  login(
    email: string,
    password: string
  ): Promise<void>;

  register(
    email: string,
    password: string,
    fullName: string
  ): Promise<void>;

  logout(): Promise<void>;

  setUser(user: User): void;
}

const AuthContext =
  createContext<AuthState | null>(null);

/* =========================================================
   TRADING BACKGROUND
========================================================= */

function TradingBackground({ showTicker = false }: { showTicker?: boolean }) {
  const candles = Array.from({ length: 36 });

  return (
    <div className="trading-bg" aria-hidden="true">
      {/* Background Grid */}
      <div className="trading-bg-grid" />

      {/* Ambient Radial Glows */}
      <div className="trading-glow trading-glow-blue" />
      <div className="trading-glow trading-glow-cyan" />
      <div className="trading-glow trading-glow-indigo" />

      {/* Decorative Equity Curve Silhouette */}
      <div className="trading-chart-wrap">
        <svg viewBox="0 0 1400 500" preserveAspectRatio="none" className="trading-chart-svg">
          <defs>
            <linearGradient id="tradebotChartFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#38BDF8" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#38BDF8" stopOpacity="0" />
            </linearGradient>
          </defs>
          <path
            d="M0 420 L60 400 L120 410 L180 360 L240 380 L300 320 L360 340 L420 280 L480 300 L540 235 L600 260 L660 205 L720 225 L780 170 L840 190 L900 140 L960 160 L1020 110 L1080 130 L1140 90 L1200 105 L1260 65 L1320 75 L1400 30 L1400 500 L0 500 Z"
            fill="url(#tradebotChartFill)"
          />
          <path
            d="M0 420 L60 400 L120 410 L180 360 L240 380 L300 320 L360 340 L420 280 L480 300 L540 235 L600 260 L660 205 L720 225 L780 170 L840 190 L900 140 L960 160 L1020 110 L1080 130 L1140 90 L1200 105 L1260 65 L1320 75 L1400 30"
            fill="none"
            stroke="#38BDF8"
            strokeWidth="2.5"
            vectorEffect="non-scaling-stroke"
          />
          <path
            d="M0 450 L140 430 L280 435 L420 395 L560 405 L700 365 L840 375 L980 330 L1120 345 L1260 300 L1400 260"
            fill="none"
            stroke="#06B6D4"
            strokeWidth="1.5"
            opacity="0.4"
            vectorEffect="non-scaling-stroke"
          />
        </svg>
      </div>

      {/* Decorative Candlesticks */}
      <div className="trading-candles-wrap">
        {candles.map((_, index) => {
          const bullish = index % 5 !== 0;
          const height = 25 + ((index * 17) % 75);
          const bottom = 18 + ((index * 13) % 35);
          const left = index * 2.7 + 1;
          return (
            <div
              key={index}
              className={`trading-candle ${bullish ? "candle-up" : "candle-down"}`}
              style={{ left: `${left}%`, bottom: `${bottom}%` }}
            >
              <div className="trading-candle-wick" style={{ height: `${height + 25}px`, top: "-12px" }} />
              <div className="trading-candle-body" style={{ height: `${height}px` }} />
            </div>
          );
        })}
      </div>

      {/* Top Market Ticker for landing / public view */}
      {showTicker && (
        <div className="trading-ticker-bar">
          <Ticker name="NIFTY 50" price="24,832.45" change="+1.24%" />
          <Divider />
          <Ticker name="BANK NIFTY" price="54,218.70" change="+0.87%" />
          <Divider />
          <Ticker name="RELIANCE" price="1,428.20" change="+1.63%" />
          <Divider />
          <Ticker name="TCS" price="3,982.15" change="+0.92%" />
        </div>
      )}

      {/* Bottom Status Bar for landing / public view */}
      {showTicker && (
        <div className="trading-status-bar">
          <Status label="Market" value="Open" color="gain" />
          <Status label="Paper" value="Active" color="info" />
          <Status label="Engine" value="Hybrid v1.2" color="cyan" />
          <Status label="Data" value="Simulated" color="warn" />
        </div>
      )}

      {/* Dark vignette overlay */}
      <div className="trading-overlay-vignette" />
    </div>
  );
}

/* =========================================================
   TICKER COMPONENT
========================================================= */

function Ticker({
  name,
  price,
  change,
}: {
  name: string;
  price: string;
  change: string;
}) {
  return (
    <div className="trading-ticker-item">
      <span className="trading-ticker-name">{name}</span>
      <span className="trading-ticker-price num">{price}</span>
      <span className="trading-ticker-change gain">{change}</span>
    </div>
  );
}

/* =========================================================
   DIVIDER
========================================================= */

function Divider() {
  return <div className="trading-ticker-divider" />;
}

/* =========================================================
   STATUS
========================================================= */

function Status({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color: string;
}) {
  return (
    <span className="trading-status-item">
      <span className="trading-status-label">{label}</span>
      <span className={`trading-status-val ${color}`}>{value}</span>
    </span>
  );
}

/* =========================================================
   AUTH PROVIDER
========================================================= */

export function AuthProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [user, setUser] =
    useState<User | null>(null);

  const [ready, setReady] =
    useState(false);

  /* -------------------------------------------------------
     RESTORE SESSION
  ------------------------------------------------------- */

  useEffect(() => {

    setLogoutHandler(() => {
      setUser(null);
    });

    let mounted = true;

    const restoreSession =
      async () => {

        try {

          /*
           * If access token doesn't exist
           * but refresh token exists,
           * try refreshing the session.
           */

          if (
            !tokens.access &&
            tokens.refresh
          ) {
            await refreshSession();
          }

          /*
           * If we now have an access token,
           * fetch the current user.
           */

          if (tokens.access) {

            const currentUser =
              await get<User>(
                "/auth/me"
              );

            if (mounted) {
              setUser(currentUser);
            }
          }

        } catch {

          /*
           * Invalid/expired session.
           */

          tokens.clear();

          if (mounted) {
            setUser(null);
          }

        } finally {

          if (mounted) {
            setReady(true);
          }

        }
      };

    restoreSession();

    return () => {
      mounted = false;
    };

  }, []);

  /* -------------------------------------------------------
     ACCEPT TOKEN RESPONSE
  ------------------------------------------------------- */

  const accept = useCallback(
    (response: TokenResponse) => {

      tokens.save(response);

      setUser(response.user);

    },
    []
  );

  /* -------------------------------------------------------
     LOGIN
  ------------------------------------------------------- */

  const login = useCallback(
    async (
      email: string,
      password: string
    ) => {

      const response =
        await post<TokenResponse>(
          "/auth/login",
          {
            email,
            password,
          }
        );

      accept(response);

    },
    [accept]
  );

  /* -------------------------------------------------------
     REGISTER
  ------------------------------------------------------- */

  const register = useCallback(
    async (
      email: string,
      password: string,
      fullName: string
    ) => {

      const response =
        await post<TokenResponse>(
          "/auth/register",
          {
            email,
            password,
            full_name: fullName,
          }
        );

      accept(response);

    },
    [accept]
  );

  /* -------------------------------------------------------
     LOGOUT
  ------------------------------------------------------- */

  const logout = useCallback(
    async () => {

      const refreshToken =
        tokens.refresh;

      /*
       * Tell backend to invalidate refresh token.
       * Even if backend request fails,
       * local session will still be cleared.
       */

      if (refreshToken) {

        await post(
          "/auth/logout",
          {
            refresh_token:
              refreshToken,
          }
        ).catch(() => undefined);

      }

      tokens.clear();

      setUser(null);

    },
    []
  );

  /* -------------------------------------------------------
     CONTEXT VALUE
  ------------------------------------------------------- */

  const value =
    useMemo<AuthState>(
      () => ({
        user,
        ready,
        login,
        register,
        logout,
        setUser,
      }),
      [
        user,
        ready,
        login,
        register,
        logout,
      ]
    );

  /* -------------------------------------------------------
     PROVIDER
  ------------------------------------------------------- */

  return (
    <AuthContext.Provider
      value={value}
    >

      {/* Premium trading background */}
      <TradingBackground showTicker={!user} />

      {/* Application content */}
      <div className="app-shell-root">
        {children}
      </div>

    </AuthContext.Provider>
  );
}

/* =========================================================
   USE AUTH
========================================================= */

export function useAuth() {

  const context =
    useContext(AuthContext);

  if (!context) {

    throw new Error(
      "useAuth must be used inside AuthProvider"
    );

  }

  return context;
}

/* =========================================================
   ADMIN CHECK
========================================================= */

export const isAdmin = (
  user: User | null
) =>
  !!user &&
  (
    user.role === "ADMIN" ||
    user.role === "SUPER_ADMIN"
  );