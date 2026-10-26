import { useEffect, useState } from "react";

export interface FetchState<T> {
  data?: T;
  dataKey?: string; // the key the current `data` belongs to
  error?: string;
  loading: boolean;
}

// Re-runs `load` whenever `key` changes. The previous data is kept while the next load is in
// flight so the screen holds its layout at reduced opacity instead of flashing a skeleton.
// Views must show `error` whenever it is set, because `data` may then belong to an older key.
export function useFetch<T>(key: string, load: () => Promise<T>): FetchState<T> {
  const [state, setState] = useState<FetchState<T>>({ loading: true });

  useEffect(() => {
    let alive = true;
    setState((s) => ({ ...s, loading: true, error: undefined }));
    load()
      .then((data) => {
        if (alive) setState({ data, dataKey: key, loading: false });
      })
      .catch((err: unknown) => {
        if (alive) {
          setState((s) => ({ ...s, loading: false, error: err instanceof Error ? err.message : String(err) }));
        }
      });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return state;
}
