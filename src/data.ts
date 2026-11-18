import { useCallback, useEffect, useRef, useState } from "react";
import type { Dataset } from "./types";

/** How often an open tab quietly checks whether the scraper has published something newer. */
const POLL_MS = 10 * 60_000;

const stamp = (d: Dataset) => d.updated ?? d.generated;

async function fetchDataset(signal?: AbortSignal): Promise<Dataset> {
  const r = await fetch("/data/listings.json", { signal, cache: "no-cache" });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return (await r.json()) as Promise<Dataset>;
}

/** "new" = newer data was found and swapped in; "same" = already the latest; "error" = couldn't tell. */
export type CheckResult = "new" | "same" | "error";

export function useDataset(): { data: Dataset | null; error: string | null; checkNow: () => Promise<CheckResult> } {
  const [data, setData] = useState<Dataset | null>(null);
  const [error, setError] = useState<string | null>(null);
  const current = useRef<string | null>(null);

  useEffect(() => {
    const ctl = new AbortController();
    fetchDataset(ctl.signal)
      .then((d) => {
        current.current = stamp(d);
        setData(d);
      })
      .catch((e: unknown) => {
        if (!ctl.signal.aborted) setError(e instanceof Error ? e.message : "Could not load listings");
      });
    return () => ctl.abort();
  }, []);

  // The scraper redeploys the site whenever it finds something. A tab left open learns about it from a
  // ~100-byte meta file and only then pulls the full listing set: no reload, no polling of the big file.
  const checkNow = useCallback(async (): Promise<CheckResult> => {
    if (current.current === null) return "error";
    try {
      const r = await fetch("/data/meta.json", { cache: "no-store" });
      if (!r.ok) return "error";
      const meta = (await r.json()) as { updated?: string; generated?: string };
      const next = meta.updated ?? meta.generated;
      if (!next) return "error";
      if (next === current.current) return "same";
      const fresh = await fetchDataset();
      current.current = stamp(fresh);
      setData(fresh);
      return "new";
    } catch {
      return "error"; // offline, or mid-deploy: the next check will catch up
    }
  }, []);

  useEffect(() => {
    const quiet = () => {
      if (!document.hidden) void checkNow();
    };
    const id = window.setInterval(quiet, POLL_MS);
    document.addEventListener("visibilitychange", quiet);
    return () => {
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", quiet);
    };
  }, [checkNow]);

  return { data, error, checkNow };
}
