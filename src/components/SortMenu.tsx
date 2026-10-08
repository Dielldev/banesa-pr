import { useCallback, useState } from "react";
import type { SortKey } from "../types";
import { SORT_OPTIONS } from "../lib/filters";
import { useDismiss } from "../lib/hooks";
import { IconCheck, IconChevron } from "./Icons";

export function SortMenu({ value, onChange }: { value: SortKey; onChange: (k: SortKey) => void }) {
  const [open, setOpen] = useState(false);
  const close = useCallback(() => setOpen(false), []);
  const ref = useDismiss<HTMLDivElement>(open, close);
  const current = SORT_OPTIONS.find((o) => o.key === value)!;
  return (
    <div className="sort" ref={ref}>
      <button className="sort-btn" aria-haspopup="listbox" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <span className="sort-lbl">Sort by:</span>
        <b>{current.label}</b>
        <IconChevron size={16} />
      </button>
      {open && (
        <ul className="menu sort-menu" role="listbox" aria-label="Sort listings">
          {SORT_OPTIONS.map((o) => (
            <li key={o.key} role="option" aria-selected={o.key === value}>
              <button
                onClick={() => {
                  onChange(o.key);
                  setOpen(false);
                }}
              >
                {o.label}
                {o.key === value && <IconCheck size={16} />}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
