import type { TierKey } from "../types";
import { IconGrid, IconMap, IconSearch, IconSliders, IconClose } from "./Icons";

interface Props {
  tier: TierKey;
  onTier: (t: TierKey) => void;
  query: string;
  onQuery: (q: string) => void;
  filterCount: number;
  onOpenFilters: () => void;
  view: "map" | "grid";
  onView: (v: "map" | "grid") => void;
}

const TIERS: { key: TierKey; label: string }[] = [
  { key: "all", label: "All" },
  { key: "core", label: "Prishtina e Re" },
  { key: "nearby", label: "Nearby" },
];

export function Toolbar({ tier, onTier, query, onQuery, filterCount, onOpenFilters, view, onView }: Props) {
  return (
    <div className="toolbar">
      <div className="tiers" role="tablist" aria-label="Area">
        {TIERS.map((t) => (
          <button key={t.key} role="tab" aria-selected={tier === t.key} onClick={() => onTier(t.key)}>
            {t.label}
          </button>
        ))}
      </div>
      <span className="vr" aria-hidden="true" />

      <div className="search">
        <label className="search-box">
          <IconSearch size={18} />
          <input
            type="search"
            value={query}
            placeholder="Search lagje, agency, keyword…"
            aria-label="Search listings"
            autoComplete="off"
            onChange={(e) => onQuery(e.target.value)}
          />
          {query && (
            <button type="button" className="clear" aria-label="Clear search" onClick={() => onQuery("")}>
              <IconClose size={14} />
            </button>
          )}
        </label>
        <button className="filter-btn" onClick={onOpenFilters} aria-label={`Filters${filterCount ? `, ${filterCount} active` : ""}`}>
          <IconSliders size={19} />
          {filterCount > 0 && <span className="badge">{filterCount}</span>}
        </button>
      </div>

      <div className="view-toggle" role="group" aria-label="View">
        <button aria-pressed={view === "map"} onClick={() => onView("map")}>
          <IconMap size={18} />
          Map
        </button>
        <button aria-pressed={view === "grid"} onClick={() => onView("grid")}>
          <IconGrid size={18} />
          Grid
        </button>
      </div>
    </div>
  );
}
