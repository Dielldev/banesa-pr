import type { Feature, Filters, Listing, SortKey } from "../types";

export const PMIN = 20_000;
export const PMAX = 500_000;

export const FEATURE_LABELS: Record<Feature, string> = {
  parking: "Parking",
  elevator: "Elevator",
  new_build: "New build",
  balcony: "Balcony",
  renovated: "Renovated",
  basement: "Basement",
  furnished: "Furnished",
  duplex: "Duplex",
  heating: "Heating",
};

export const ROOM_OPTIONS: { value: number; label: string }[] = [
  { value: 0, label: "Studio" },
  { value: 1, label: "1 bed" },
  { value: 2, label: "2 beds" },
  { value: 3, label: "3 beds" },
  { value: 4, label: "4+ beds" },
];

export const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: "score", label: "Best value" },
  { key: "new", label: "Latest" },
  { key: "price", label: "Price: low to high" },
  { key: "priced", label: "Price: high to low" },
  { key: "ppm", label: "€/m²: lowest" },
  { key: "area", label: "Size: largest" },
];

export const DEFAULT_FILTERS: Filters = {
  q: "",
  segment: "all",
  tier: "all",
  hoods: [],
  rooms: [],
  feats: [],
  agency: "",
  pmin: PMIN,
  pmax: PMAX,
  amin: null,
  amax: null,
  from: null,
  to: null,
  preset: null,
  undated: false,
  sort: "score",
};

const ts = (l: Listing) => (l.date ? Date.parse(l.date + "T00:00:00") : -1);

const SORTS: Record<SortKey, (a: Listing, b: Listing) => number> = {
  score: (a, b) => (b.score ?? -1) - (a.score ?? -1),
  new: (a, b) => ts(b) - ts(a) || (b.score ?? -1) - (a.score ?? -1),
  price: (a, b) => (a.price ?? 1e12) - (b.price ?? 1e12),
  priced: (a, b) => (b.price ?? -1) - (a.price ?? -1),
  ppm: (a, b) => (a.eur_m2 ?? 1e12) - (b.eur_m2 ?? 1e12),
  area: (a, b) => (b.area ?? -1) - (a.area ?? -1),
};

export function applyFilters(all: Listing[], f: Filters, saved: ReadonlySet<string>): Listing[] {
  const q = f.q.trim().toLowerCase();
  const hoods = new Set(f.hoods);
  const priceOn = f.pmin > PMIN || f.pmax < PMAX;
  const out = all.filter((l) => {
    if (f.segment === "prio" && !l.prio) return false;
    if (f.segment === "saved" && !saved.has(l.id)) return false;
    if (f.tier !== "all" && l.tier !== f.tier) return false;
    if (hoods.size && !(l.hood && hoods.has(l.hood))) return false;
    if (f.rooms.length) {
      if (l.rooms == null) return false;
      if (!f.rooms.some((r) => (r >= 4 ? l.rooms! >= 4 : l.rooms === r))) return false;
    }
    if (f.feats.length && !f.feats.every((k) => l.features?.includes(k))) return false;
    if (f.agency && l.agency !== f.agency) return false;
    if (priceOn && (l.price == null || l.price < f.pmin || l.price > f.pmax)) return false;
    if (f.from || f.to) {
      if (!l.date) return f.undated;
      if (f.from && l.date < f.from) return false;
      if (f.to && l.date > f.to) return false;
    }
    if (f.amin != null && (l.area == null || l.area < f.amin)) return false;
    if (f.amax != null && (l.area == null || l.area > f.amax)) return false;
    if (q) {
      const hay = `${l.title} ${l.hood ?? ""} ${l.agency ?? ""} ${l.description ?? ""}`.toLowerCase();
      if (!q.split(/\s+/).every((w) => hay.includes(w))) return false;
    }
    return true;
  });
  return out.sort(SORTS[f.sort]);
}

export function median(nums: number[]): number | null {
  if (!nums.length) return null;
  const s = [...nums].sort((a, b) => a - b);
  return s[Math.floor(s.length / 2)]!;
}

/** Number of filter groups that differ from the defaults (search and sort excluded). */
export function activeCount(f: Filters): number {
  return (
    (f.hoods.length ? 1 : 0) +
    (f.rooms.length ? 1 : 0) +
    (f.feats.length ? 1 : 0) +
    (f.agency ? 1 : 0) +
    (f.pmin > PMIN || f.pmax < PMAX ? 1 : 0) +
    (f.amin != null || f.amax != null ? 1 : 0) +
    (f.from || f.to ? 1 : 0)
  );
}

/* ---------- URL <-> filters, so a view can be shared as a link ---------- */

export function toParams(f: Filters): URLSearchParams {
  const p = new URLSearchParams();
  const d = DEFAULT_FILTERS;
  if (f.q) p.set("q", f.q);
  if (f.segment !== d.segment) p.set("seg", f.segment);
  if (f.tier !== d.tier) p.set("tier", f.tier);
  if (f.hoods.length) p.set("hood", f.hoods.join("~"));
  if (f.rooms.length) p.set("rooms", f.rooms.join(","));
  if (f.feats.length) p.set("feat", f.feats.join(","));
  if (f.agency) p.set("agency", f.agency);
  if (f.pmin > PMIN) p.set("pmin", String(f.pmin));
  if (f.pmax < PMAX) p.set("pmax", String(f.pmax));
  if (f.amin != null) p.set("amin", String(f.amin));
  if (f.amax != null) p.set("amax", String(f.amax));
  if (f.from) p.set("from", f.from);
  if (f.to) p.set("to", f.to);
  if (f.preset) p.set("preset", f.preset);
  if (f.undated) p.set("undated", "1");
  if (f.sort !== d.sort) p.set("sort", f.sort);
  return p;
}

const num = (v: string | null): number | null => {
  if (v == null || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};

export function fromParams(p: URLSearchParams): Filters {
  const d = DEFAULT_FILTERS;
  const pick = <T extends string>(v: string | null, ok: readonly T[], fb: T): T =>
    ok.includes(v as T) ? (v as T) : fb;
  const feats = Object.keys(FEATURE_LABELS) as Feature[];
  return {
    q: p.get("q") ?? "",
    segment: pick(p.get("seg"), ["all", "prio", "saved"] as const, d.segment),
    tier: pick(p.get("tier"), ["all", "core", "nearby"] as const, d.tier),
    hoods: p.get("hood")?.split("~").filter(Boolean) ?? [],
    rooms: (p.get("rooms")?.split(",").map(Number) ?? []).filter((n) => Number.isInteger(n) && n >= 0 && n <= 4),
    feats: (p.get("feat")?.split(",") ?? []).filter((k): k is Feature => feats.includes(k as Feature)),
    agency: p.get("agency") ?? "",
    pmin: Math.max(PMIN, num(p.get("pmin")) ?? PMIN),
    pmax: Math.min(PMAX, num(p.get("pmax")) ?? PMAX),
    amin: num(p.get("amin")),
    amax: num(p.get("amax")),
    from: p.get("from"),
    to: p.get("to"),
    preset: p.get("preset"),
    undated: p.get("undated") === "1",
    sort: pick(p.get("sort"), SORT_OPTIONS.map((o) => o.key), d.sort),
  };
}
