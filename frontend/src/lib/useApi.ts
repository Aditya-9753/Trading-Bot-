import { useCallback, useEffect, useRef, useState } from "react";
import { get } from "../api/client";

/** GET with loading/error state; `reload()` refetches without flashing the loading state. */
export function useApi<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(!!path);
  const seq = useRef(0);
  const reload = useCallback(async () => {
    if (!path) return;
    const id = ++seq.current;
    try {
      const d = await get<T>(path);
      if (id === seq.current) { setData(d); setError(null); }
    } catch (e) {
      if (id === seq.current) setError((e as Error).message);
    } finally {
      if (id === seq.current) setLoading(false);
    }
  }, [path]);
  useEffect(() => { setLoading(!!path); void reload(); }, [reload, path]);
  return { data, error, loading, reload, setData };
}
