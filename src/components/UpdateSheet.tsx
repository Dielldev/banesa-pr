import { useEffect, useRef } from "react";
import type { UpdaterState } from "../lib/updater";
import { useScrollLock } from "../lib/hooks";
import { IconCheck, IconClose, IconRefresh } from "./Icons";

interface Props {
  state: UpdaterState;
  updatedText: string;
  total: number;
  onStart: () => void;
  onClose: () => void;
}

/** One big button, plain words. Everything else on the screen just reports what's happening. */
export function UpdateSheet({ state, updatedText, total, onStart, onClose }: Props) {
  useScrollLock(true);
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    closeRef.current?.focus();
    const key = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", key);
    return () => document.removeEventListener("keydown", key);
  }, [onClose]);

  const busy = state.phase === "checking" || state.phase === "running" || state.phase === "publishing";
  const done = state.phase === "done";

  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="sheet update-sheet" role="dialog" aria-modal="true" aria-label="Check for new listings">
        <header className="sheet-head">
          <h2>New listings</h2>
          <button ref={closeRef} className="round-btn" onClick={onClose} aria-label="Close">
            <IconClose size={16} />
          </button>
        </header>

        <div className="update-body" aria-live="polite">
          <div className={`update-icon${busy ? " spin" : ""}${done ? ` ${state.outcome}` : ""}`}>
            {done && state.outcome !== "error" ? <IconCheck size={30} /> : <IconRefresh size={30} />}
          </div>

          {busy && (
            <>
              <p className="update-title">{state.message}</p>
              <p className="update-sub">
                {state.phase === "running"
                  ? "This usually takes 1–3 minutes. You can close this, we'll tell you when it's done."
                  : "Just a moment…"}
              </p>
            </>
          )}

          {done && (
            <>
              <p className="update-title">{state.message}</p>
              <p className="update-sub">
                {state.outcome === "new"
                  ? "Look for the blue New tag, or sort by Latest."
                  : `${total.toLocaleString("en-US")} homes · last changed ${updatedText}`}
              </p>
            </>
          )}

          {state.phase === "idle" && (
            <>
              <p className="update-title">{total.toLocaleString("en-US")} homes</p>
              <p className="update-sub">
                Last updated {updatedText}. The site looks for new ads by itself every hour. Tap below to look right now.
              </p>
            </>
          )}
        </div>

        <footer className="sheet-foot update-foot">
          {done ? (
            <>
              <button className="btn-outline" onClick={onClose}>
                Close
              </button>
              <button className="btn-primary" onClick={onStart}>
                Check again
              </button>
            </>
          ) : (
            <button className="btn-primary" onClick={onStart} disabled={busy}>
              <IconRefresh size={18} />
              {busy ? "Looking…" : "Check for new listings"}
            </button>
          )}
        </footer>
      </div>
    </div>
  );
}
