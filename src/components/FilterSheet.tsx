import { useEffect, useRef } from "react";
import type { Feature, Filters } from "../types";
import { FEATURE_LABELS, PMAX, PMIN, ROOM_OPTIONS } from "../lib/filters";
import type { DatePreset } from "../lib/dates";
import { eur } from "../lib/format";
import { useScrollLock } from "../lib/hooks";
import { DualRange } from "./DualRange";
import { IconClose } from "./Icons";

export interface FilterMeta {
  hoods: { name: string; count: number }[];
  agencies: string[];
  presets: (DatePreset & { count: number })[];
  undated: number;
  dateMin: string | null;
  dateMax: string | null;
}

interface Props {
  filters: Filters;
  meta: FilterMeta;
  resultCount: number;
  onChange: (patch: Partial<Filters>) => void;
  onReset: () => void;
  onClose: () => void;
}

const toggle = <T,>(list: T[], v: T): T[] => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);

export function FilterSheet({ filters: f, meta, resultCount, onChange, onReset, onClose }: Props) {
  useScrollLock(true);
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    closeRef.current?.focus();
    const key = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", key);
    return () => document.removeEventListener("keydown", key);
  }, [onClose]);

  const numInput = (v: string): number | null => (v === "" ? null : Math.max(0, Number(v)));

  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="sheet" role="dialog" aria-modal="true" aria-label="Filters">
        <header className="sheet-head">
          <h2>Filters</h2>
          <button ref={closeRef} className="round-btn" onClick={onClose} aria-label="Close filters">
            <IconClose size={16} />
          </button>
        </header>

        <div className="sheet-body">
          <section>
            <h3>Price range</h3>
            <DualRange min={PMIN} max={PMAX} step={5000} lo={f.pmin} hi={f.pmax} label="price" onChange={(pmin, pmax) => onChange({ pmin, pmax })} />
            <div className="range-ends">
              <span>{eur(f.pmin)}</span>
              <span>{f.pmax >= PMAX ? `${eur(PMAX)}+` : eur(f.pmax)}</span>
            </div>
          </section>

          <section>
            <h3>Surface area</h3>
            <div className="pair">
              <input type="number" inputMode="numeric" min={0} placeholder="Min m²" aria-label="Minimum area" value={f.amin ?? ""} onChange={(e) => onChange({ amin: numInput(e.target.value) })} />
              <span>–</span>
              <input type="number" inputMode="numeric" min={0} placeholder="Max m²" aria-label="Maximum area" value={f.amax ?? ""} onChange={(e) => onChange({ amax: numInput(e.target.value) })} />
            </div>
          </section>

          <section>
            <h3>Bedrooms</h3>
            <div className="pills">
              {ROOM_OPTIONS.map((o) => (
                <button key={o.value} className="pill" aria-pressed={f.rooms.includes(o.value)} onClick={() => onChange({ rooms: toggle(f.rooms, o.value) })}>
                  {o.label}
                </button>
              ))}
            </div>
          </section>

          <section>
            <h3>Lagjja</h3>
            <div className="checks">
              {meta.hoods.map((h) => (
                <label key={h.name} className="check">
                  <input type="checkbox" checked={f.hoods.includes(h.name)} onChange={() => onChange({ hoods: toggle(f.hoods, h.name) })} />
                  <span>{h.name}</span>
                  <em>{h.count}</em>
                </label>
              ))}
            </div>
          </section>

          <section>
            <h3>Amenities</h3>
            <div className="pills">
              {(Object.keys(FEATURE_LABELS) as Feature[]).map((k) => (
                <button key={k} className="pill" aria-pressed={f.feats.includes(k)} onClick={() => onChange({ feats: toggle(f.feats, k) })}>
                  {FEATURE_LABELS[k]}
                </button>
              ))}
            </div>
          </section>

          <section>
            <h3>Published</h3>
            <div className="pills">
              {meta.presets.map((p) => (
                <button
                  key={p.key}
                  className="pill"
                  aria-pressed={f.preset === p.key}
                  onClick={() => (f.preset === p.key ? onChange({ preset: null, from: null, to: null }) : onChange({ preset: p.key, from: p.from, to: p.to }))}
                >
                  {p.label}
                  <small>{p.count}</small>
                </button>
              ))}
            </div>
            <div className="pair dates">
              <label>
                <span>From</span>
                <input type="date" min={meta.dateMin ?? undefined} max={meta.dateMax ?? undefined} value={f.from ?? ""} onChange={(e) => onChange({ from: e.target.value || null, preset: null })} />
              </label>
              <label>
                <span>To</span>
                <input type="date" min={meta.dateMin ?? undefined} max={meta.dateMax ?? undefined} value={f.to ?? ""} onChange={(e) => onChange({ to: e.target.value || null, preset: null })} />
              </label>
            </div>
            <label className="check inline">
              <input type="checkbox" checked={f.undated} onChange={(e) => onChange({ undated: e.target.checked })} />
              <span>Include ads with no date</span>
              <em>{meta.undated}</em>
            </label>
          </section>

          <section>
            <h3>Agency</h3>
            <select value={f.agency} aria-label="Agency" onChange={(e) => onChange({ agency: e.target.value })}>
              <option value="">All agencies</option>
              {meta.agencies.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </section>
        </div>

        <footer className="sheet-foot">
          <button className="btn-ghost" onClick={onReset}>
            Clear all
          </button>
          <button className="btn-primary" onClick={onClose}>
            Show {resultCount.toLocaleString("en-US")} {resultCount === 1 ? "home" : "homes"}
          </button>
        </footer>
      </div>
    </div>
  );
}
