import { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import type { Dataset, Filters, Listing, SegmentKey } from "./types";
import { useDataset } from "./data";
import { activeCount, applyFilters, DEFAULT_FILTERS, FEATURE_LABELS, fromParams, median, toParams } from "./lib/filters";
import { datePresets, generatedLabel, makeClock, type Clock } from "./lib/dates";
import { placeListings } from "./lib/geo";
import { eur } from "./lib/format";
import { useMedia, useStoredSet } from "./lib/hooks";
import { Header } from "./components/Header";
import { Toolbar } from "./components/Toolbar";
import { SortMenu } from "./components/SortMenu";
import { ListingCard } from "./components/ListingCard";
import { MapView } from "./components/MapView";
import { MapPopup } from "./components/MapPopup";
import { FilterSheet, type FilterMeta } from "./components/FilterSheet";
import { DetailDrawer } from "./components/DetailDrawer";
import { IconClose, IconHeart } from "./components/Icons";

const PAGE = 24;
const MAP_PINS_CAP = 400;

function initialFilters(): Filters {
  return fromParams(new URLSearchParams(window.location.search));
}

export function App() {
  const { data, error } = useDataset();
  if (error) {
    return (
      <div className="state">
        <h1>Couldn't load the listings</h1>
        <p>{error}</p>
        <button className="btn-primary" onClick={() => window.location.reload()}>
          Try again
        </button>
      </div>
    );
  }
  if (!data) return <Skeleton />;
  return <Board data={data} />;
}

function Skeleton() {
  return (
    <div className="skeleton" role="status" aria-label="Loading listings">
      <div className="sk-bar" />
      <div className="sk-grid">
        {Array.from({ length: 6 }, (_, i) => (
          <div key={i} className="sk-card" />
        ))}
      </div>
    </div>
  );
}

function Board({ data }: { data: Dataset }) {
  const all = data.listings;
  const clock = useMemo<Clock>(() => makeClock(data.generated), [data.generated]);
  const byId = useMemo(() => new Map(all.map((l) => [l.id, l])), [all]);
  const positions = useMemo(() => placeListings(all), [all]);

  const isDesktop = useMedia("(min-width: 1024px)");
  const [saved, toggleSaved, clearSaved] = useStoredSet("banesa.saved");
  const [filters, setFilters] = useState<Filters>(initialFilters);
  const [view, setView] = useState<"map" | "grid">(() => (window.matchMedia("(min-width: 1024px)").matches ? "map" : "grid"));
  const [expanded, setExpanded] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [openId, setOpenId] = useState<string | null>(() => new URLSearchParams(window.location.search).get("l"));
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [visible, setVisible] = useState(PAGE);
  const listRef = useRef<HTMLElement>(null);
  const sentinel = useRef<HTMLDivElement>(null);

  const patch = useCallback((p: Partial<Filters>) => setFilters((f) => ({ ...f, ...p })), []);
  const query = useDeferredValue(filters.q);
  const effective = useMemo(() => ({ ...filters, q: query }), [filters, query]);

  const results = useMemo(() => applyFilters(all, effective, saved), [all, effective, saved]);

  // facets for the filter sheet and header counts
  const meta = useMemo<FilterMeta>(() => {
    const hoodCount = new Map<string, number>();
    for (const l of all) if (l.hood) hoodCount.set(l.hood, (hoodCount.get(l.hood) ?? 0) + 1);
    const dates = all.map((l) => l.date).filter((d): d is string => !!d).sort();
    return {
      hoods: [...hoodCount].map(([name, count]) => ({ name, count })).sort((a, b) => b.count - a.count),
      agencies: [...new Set(all.map((l) => l.agency).filter((a): a is string => !!a))].sort(),
      presets: datePresets(all, clock).map((p) => ({
        ...p,
        count: all.filter((l) => l.date && l.date >= p.from && (!p.to || l.date <= p.to)).length,
      })),
      undated: all.filter((l) => !l.date).length,
      dateMin: dates[0] ?? null,
      dateMax: dates.at(-1) ?? null,
    };
  }, [all, clock]);

  const segmentCounts = useMemo<Record<SegmentKey, number>>(
    () => ({ all: all.length, prio: all.filter((l) => l.prio).length, saved: all.filter((l) => saved.has(l.id)).length }),
    [all, saved],
  );

  const asOf = generatedLabel(data);
  const newest = useMemo(
    () =>
      all
        .filter((l) => l.date && clock.daysSince(l.date) <= 7)
        .sort((a, b) => (b.date! < a.date! ? -1 : b.date! > a.date! ? 1 : (b.score ?? 0) - (a.score ?? 0)))
        .slice(0, 6)
        .map((l) => ({ listing: l, days: clock.daysSince(l.date!) })),
    [all, clock],
  );

  const daysOld = useCallback((l: Listing) => (l.date ? clock.daysSince(l.date) : null), [clock]);

  // a new result set restarts the list and the map framing
  const signature = useMemo(() => toParams({ ...effective, sort: effective.sort }).toString() + `|${saved.size}`, [effective, saved.size]);
  const fitKey = useMemo(() => signature + `|${view}|${expanded}`, [signature, view, expanded]);
  useEffect(() => {
    setVisible(PAGE);
    listRef.current?.scrollTo({ top: 0 });
  }, [signature]);

  // keep the address bar in step with the view, so the link is shareable
  useEffect(() => {
    const p = toParams(filters);
    if (openId) p.set("l", openId);
    const qs = p.toString();
    window.history.replaceState(null, "", qs ? `?${qs}` : window.location.pathname);
  }, [filters, openId]);

  // infinite list
  useEffect(() => {
    const el = sentinel.current;
    if (!el) return;
    const io = new IntersectionObserver(
      (entries) => entries[0]?.isIntersecting && setVisible((v) => v + PAGE),
      { rootMargin: "600px 0px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [results.length, view, expanded]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 2400);
    return () => clearTimeout(t);
  }, [toast]);

  const shown = results.slice(0, visible);
  const mapOnly = view === "map" && !isDesktop;
  const pinItems = useMemo(
    () => results.slice(0, Math.min(Math.max(visible, mapOnly ? 80 : PAGE), MAP_PINS_CAP)),
    [results, visible, mapOnly],
  );
  const selected = selectedId ? byId.get(selectedId) ?? null : null;
  const opened = openId ? byId.get(openId) ?? null : null;

  const showMap = view === "map" || expanded;
  const showList = !expanded;

  const onOpen = useCallback((id: string) => setOpenId(id), []);
  const closeOpen = useCallback(() => setOpenId(null), []);
  const onHover = useCallback((id: string | null) => setHoveredId(id), []);
  const onShowOnMap = useCallback((id: string) => {
    setView("map");
    setSelectedId(id);
  }, []);
  const onSelectPin = useCallback(
    (id: string | null) => {
      setSelectedId(id);
      if (id && isDesktop) {
        document.querySelector(`[data-id="${CSS.escape(id)}"]`)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
      }
    },
    [isDesktop],
  );

  const share = async () => {
    const p = toParams(filters);
    const url = `${window.location.origin}${window.location.pathname}${p.toString() ? `?${p}` : ""}`;
    try {
      await navigator.clipboard.writeText(url);
      setToast("Link to this view copied");
    } catch {
      window.prompt("Copy this link", url);
    }
  };

  const filterCount = activeCount(filters);
  const place = filters.hoods.length === 1 ? filters.hoods[0]! : filters.tier === "core" ? "Prishtina e Re" : "Prishtina e Re & nearby";
  const med = median(results.map((l) => l.eur_m2).filter((n): n is number => n != null));

  const chips = useMemo(() => {
    const out: { key: string; label: string; clear: () => void }[] = [];
    filters.hoods.forEach((h) => out.push({ key: "h" + h, label: h, clear: () => patch({ hoods: filters.hoods.filter((x) => x !== h) }) }));
    if (filters.pmin > DEFAULT_FILTERS.pmin || filters.pmax < DEFAULT_FILTERS.pmax) {
      const hi = filters.pmax >= DEFAULT_FILTERS.pmax ? "+" : ` – ${eur(filters.pmax)}`;
      out.push({ key: "price", label: `${eur(filters.pmin)}${hi}`, clear: () => patch({ pmin: DEFAULT_FILTERS.pmin, pmax: DEFAULT_FILTERS.pmax }) });
    }
    if (filters.amin != null || filters.amax != null)
      out.push({ key: "area", label: `${filters.amin ?? 0}–${filters.amax ?? "∞"} m²`, clear: () => patch({ amin: null, amax: null }) });
    if (filters.rooms.length)
      out.push({ key: "rooms", label: filters.rooms.map((r) => (r === 0 ? "Studio" : r >= 4 ? "4+ beds" : `${r} bed`)).join(", "), clear: () => patch({ rooms: [] }) });
    if (filters.feats.length) out.push({ key: "feats", label: filters.feats.length === 1 ? FEATURE_LABELS[filters.feats[0]!] : `${filters.feats.length} amenities`, clear: () => patch({ feats: [] }) });
    if (filters.agency) out.push({ key: "agency", label: filters.agency, clear: () => patch({ agency: "" }) });
    if (filters.from || filters.to)
      out.push({ key: "date", label: meta.presets.find((p) => p.key === filters.preset)?.label ?? `${filters.from ?? "…"} → ${filters.to ?? "…"}`, clear: () => patch({ from: null, to: null, preset: null, undated: false }) });
    return out;
  }, [filters, meta.presets, patch]);

  const resetFilters = () => setFilters((f) => ({ ...DEFAULT_FILTERS, q: f.q, sort: f.sort, segment: f.segment, tier: f.tier }));

  return (
    <div className={`app${expanded ? " is-expanded" : ""}`} data-view={view}>
      <Header
        segment={filters.segment}
        counts={segmentCounts}
        onSegment={(segment) => patch({ segment })}
        onShare={share}
        newest={newest}
        asOf={asOf}
        total={all.length}
        savedCount={saved.size}
        onOpen={onOpen}
        onShowSaved={() => patch({ segment: "saved" })}
        onClearSaved={clearSaved}
      />

      <Toolbar
        tier={filters.tier}
        onTier={(tier) => patch({ tier })}
        query={filters.q}
        onQuery={(q) => patch({ q })}
        filterCount={filterCount}
        onOpenFilters={() => setFiltersOpen(true)}
        view={view}
        onView={(v) => {
          setView(v);
          setExpanded(false);
        }}
      />

      <main className="page">
        <div className="titlebar">
          <div>
            <h1>{place} Apartments</h1>
            <p className="count" aria-live="polite">
              {results.length.toLocaleString("en-US")} {results.length === 1 ? "home" : "homes"} found
              {med != null && <span className="count-med"> · median {eur(med)}/m²</span>}
            </p>
          </div>
          <SortMenu value={filters.sort} onChange={(sort) => patch({ sort })} />
        </div>

        {chips.length > 0 && (
          <div className="chips" aria-label="Active filters">
            {chips.map((c) => (
              <button key={c.key} className="chip" onClick={c.clear} aria-label={`Remove filter ${c.label}`}>
                {c.label}
                <IconClose size={13} />
              </button>
            ))}
            <button className="chip-clear" onClick={resetFilters}>
              Clear all
            </button>
          </div>
        )}

        <div className={`split${showMap && showList ? " with-map" : ""}${expanded ? " map-only" : ""}`}>
          {showList && (
            <section className="list" ref={listRef} aria-label="Listings" hidden={mapOnly}>
              {results.length === 0 ? (
                <div className="empty">
                  <IconHeart size={28} />
                  <h3>{filters.segment === "saved" ? "Nothing saved yet" : "No homes match"}</h3>
                  <p>
                    {filters.segment === "saved"
                      ? "Tap the heart on a listing to keep it here."
                      : "Try widening the price or size range, or clear a filter."}
                  </p>
                  {filters.segment !== "saved" && (
                    <button className="btn-outline" onClick={resetFilters}>
                      Clear filters
                    </button>
                  )}
                </div>
              ) : (
                <div className="cards">
                  {shown.map((l) => (
                    <ListingCard
                      key={l.id}
                      listing={l}
                      saved={saved.has(l.id)}
                      active={l.id === selectedId}
                      daysOld={daysOld(l)}
                      onOpen={onOpen}
                      onToggleSave={toggleSaved}
                      onShowOnMap={onShowOnMap}
                      onHover={onHover}
                    />
                  ))}
                </div>
              )}
              {shown.length < results.length && (
                <div ref={sentinel} className="more">
                  <button className="btn-outline" onClick={() => setVisible((v) => v + PAGE)}>
                    Show more · {(results.length - shown.length).toLocaleString("en-US")} left
                  </button>
                </div>
              )}
            </section>
          )}

          {showMap && (
            <section className="mapcol" aria-label="Map">
              <MapView
                items={pinItems}
                positions={positions}
                selectedId={selectedId}
                hoveredId={hoveredId}
                fitKey={fitKey}
                expanded={expanded}
                onSelect={onSelectPin}
                onToggleExpand={() => setExpanded((e) => !e)}
              >
                {selected && (
                  <MapPopup
                    listing={selected}
                    saved={saved.has(selected.id)}
                    onOpen={onOpen}
                    onToggleSave={toggleSaved}
                    onClose={() => setSelectedId(null)}
                  />
                )}
              </MapView>
            </section>
          )}
        </div>
      </main>

      {filtersOpen && (
        <FilterSheet
          filters={filters}
          meta={meta}
          resultCount={results.length}
          onChange={patch}
          onReset={resetFilters}
          onClose={() => setFiltersOpen(false)}
        />
      )}

      {opened && (
        <DetailDrawer
          listing={opened}
          saved={saved.has(opened.id)}
          daysOld={daysOld(opened)}
          onToggleSave={toggleSaved}
          onClose={closeOpen}
        />
      )}

      {toast && (
        <div className="toast" role="status">
          {toast}
        </div>
      )}
    </div>
  );
}
