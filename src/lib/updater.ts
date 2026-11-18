import { useCallback, useEffect, useRef, useState } from "react";
import type { CheckResult } from "../data";

/** What /api/refresh reports about the latest "Update listings" run (see api/refresh.js). */
interface RunStatus {
  state: "idle" | "queued" | "running" | "done";
  changed: boolean | null;
  conclusion?: string | null;
  runId: number | null;
  canTrigger: boolean;
  started?: boolean;
  recent?: boolean;
  previousRunId?: number | null;
}

export type Phase = "idle" | "checking" | "running" | "publishing" | "done";
export type Outcome = "new" | "same" | "error";

export interface UpdaterState {
  phase: Phase;
  outcome: Outcome | null;
  message: string | null;
  /** when the last run ended; changes every time, even if the outcome repeats */
  finishedAt: number | null;
  /** null until the API has answered once; false = this deployment can only check, not start, updates */
  canTrigger: boolean | null;
}

const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

async function api(method: "GET" | "POST"): Promise<RunStatus | null> {
  try {
    const r = await fetch("/api/refresh", { method, cache: "no-store" });
    if (!r.ok && r.status !== 501) return null;
    const type = r.headers.get("content-type") ?? "";
    return type.includes("json") ? ((await r.json()) as RunStatus) : null; // dev server answers with HTML
  } catch {
    return null;
  }
}

const RUN_LIMIT_MS = 12 * 60_000;
const DEPLOY_LIMIT_MS = 5 * 60_000;

/**
 * The "Update" button. If the site can start the GitHub workflow it does, follows it to the end and then
 * waits for the redeployed data; otherwise it simply fetches the newest published data right now.
 */
export function useUpdater(checkNow: () => Promise<CheckResult>) {
  const [state, setState] = useState<UpdaterState>({ phase: "idle", outcome: null, message: null, finishedAt: null, canTrigger: null });
  const busy = useRef(false);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  const put = useCallback((patch: Partial<UpdaterState>) => alive.current && setState((s) => ({ ...s, ...patch })), []);
  const finish = useCallback(
    (outcome: Outcome, message: string) => {
      busy.current = false;
      put({ phase: "done", outcome, message, finishedAt: Date.now() });
    },
    [put],
  );

  const waitForData = useCallback(async (): Promise<CheckResult> => {
    const until = Date.now() + DEPLOY_LIMIT_MS;
    for (;;) {
      const r = await checkNow();
      if (r === "new" || Date.now() > until) return r;
      await sleep(8000);
    }
  }, [checkNow]);

  const start = useCallback(async () => {
    if (busy.current) return;
    busy.current = true;
    put({ phase: "checking", outcome: null, message: "Getting the latest listings…" });

    const before = await api("GET");
    if (before) put({ canTrigger: before.canTrigger });

    let follow = Boolean(before && (before.state === "queued" || before.state === "running"));
    let skipRunId: number | null = null;
    let final: RunStatus | null = null;

    if (!follow && before?.canTrigger) {
      const t = await api("POST");
      if (!t) return finish("error", "Couldn't start the update. Please try again in a minute.");
      if (t.started) {
        follow = true;
        skipRunId = t.previousRunId ?? before.runId;
      } else if (t.recent || t.state === "queued" || t.state === "running") {
        follow = t.state !== "done";
        final = t.state === "done" ? t : null;
      }
    }

    if (follow) {
      put({ phase: "running", message: "Searching the listing sites for new homes…" });
      const until = Date.now() + RUN_LIMIT_MS;
      const newRunBy = Date.now() + 90_000;
      for (;;) {
        await sleep(6000);
        if (!alive.current) return;
        const s = await api("GET");
        const stale = s?.runId != null && s.runId === skipRunId; // the previous run is still the newest
        if (s && !stale && s.state === "done") {
          final = s;
          break;
        }
        if (stale && Date.now() > newRunBy) return finish("error", "The update didn't start. Please try again.");
        if (Date.now() > until) return finish("error", "This is taking longer than usual. Check back in a few minutes.");
      }
    }

    if (final && final.conclusion && final.conclusion !== "success") {
      return finish("error", "The update hit a problem. It will retry automatically within the hour.");
    }
    if (final && final.changed === false) {
      const r = await checkNow(); // may still pick up an earlier publish
      return finish(r === "new" ? "new" : "same", r === "new" ? "Found new listings." : "You're up to date. Nothing new right now.");
    }

    if (final) put({ phase: "publishing", message: "Found new listings. Publishing them…" });
    const r = await (final ? waitForData() : checkNow());
    if (r === "new") return finish("new", "Found new listings.");
    if (r === "error") return finish("error", "Couldn't reach the site. Check your connection and try again.");
    return finish("same", "You're up to date. The site also checks by itself every hour.");
  }, [checkNow, finish, put, waitForData]);

  const reset = useCallback(() => {
    if (!busy.current) put({ phase: "idle", outcome: null, message: null });
  }, [put]);

  return { state, start, reset };
}
