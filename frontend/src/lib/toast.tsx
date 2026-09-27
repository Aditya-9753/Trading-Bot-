import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

type Kind = "info" | "success" | "error";
interface Toast { id: number; title: string; body?: string; kind: Kind }
type Fn = (title: string, kind?: Kind, body?: string) => void;
const Ctx = createContext<Fn>(() => {});
let seq = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback<Fn>((title, kind = "info", body) => {
    const id = ++seq;
    setItems((xs) => [...xs.slice(-3), { id, title, body, kind }]);
    setTimeout(() => setItems((xs) => xs.filter((x) => x.id !== id)), kind === "error" ? 8000 : 4500);
  }, []);
  return (
    <Ctx.Provider value={push}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={`toast toast-${t.kind}`}>
            <strong>{t.title}</strong>
            {t.body && <span>{t.body}</span>}
            <button aria-label="Dismiss" onClick={() => setItems((xs) => xs.filter((x) => x.id !== t.id))}>×</button>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}
export const useToast = () => useContext(Ctx);
