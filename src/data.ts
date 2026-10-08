import { useEffect, useState } from "react";
import type { Dataset } from "./types";

export function useDataset(): { data: Dataset | null; error: string | null } {
  const [data, setData] = useState<Dataset | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const ctl = new AbortController();
    fetch("/data/listings.json", { signal: ctl.signal })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<Dataset>;
      })
      .then(setData)
      .catch((e: unknown) => {
        if (!ctl.signal.aborted) setError(e instanceof Error ? e.message : "Could not load listings");
      });
    return () => ctl.abort();
  }, []);
  return { data, error };
}
