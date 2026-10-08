import { useEffect, useRef, useState, type ReactNode } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { Listing } from "../types";
import type { LatLng } from "../lib/geo";
import { PRISTINA } from "../lib/geo";
import { eur } from "../lib/format";
import { useDismiss } from "../lib/hooks";
import { IconCheck, IconExpand, IconLayers, IconLocate, IconMinus, IconPlus, IconShrink } from "./Icons";

type BaseKey = "light" | "streets" | "satellite";

const BASES: Record<BaseKey, { label: string; url: string; attribution: string; subdomains?: string }> = {
  light: {
    label: "Light",
    url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  },
  streets: {
    label: "Streets",
    url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  },
  satellite: {
    label: "Satellite",
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attribution: "Tiles &copy; Esri",
  },
};

const pinLabel = (l: Listing): string => (l.price ? (l.price_derived ? "~" : "") + eur(l.price) : "Ask");
const pinShort = (l: Listing): string => {
  if (!l.price) return "Ask";
  const k = l.price >= 1e6 ? `${(l.price / 1e6).toFixed(1)}M` : `${Math.round(l.price / 1000)}k`;
  return `${l.price_derived ? "~" : ""}€${k}`;
};

function pinIcon(l: Listing): L.DivIcon {
  return L.divIcon({
    className: "pin-wrap",
    html: `<div class="pin"><span class="pin-pill"><span class="full">${pinLabel(l)}</span><span class="short">${pinShort(l)}</span></span><span class="pin-dot"></span></div>`,
    iconSize: [0, 0],
  });
}

interface Props {
  items: Listing[];
  positions: ReadonlyMap<string, LatLng>;
  selectedId: string | null;
  hoveredId: string | null;
  /** changes whenever the result set changes (not when more pages load) — triggers a re-fit */
  fitKey: string;
  expanded: boolean;
  onSelect: (id: string | null) => void;
  onToggleExpand: () => void;
  children?: ReactNode;
}

export function MapView({ items, positions, selectedId, hoveredId, fitKey, expanded, onSelect, onToggleExpand, children }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const tiles = useRef<L.TileLayer | null>(null);
  const pins = useRef<L.LayerGroup | null>(null);
  const markers = useRef(new Map<string, L.Marker>());
  const me = useRef<L.CircleMarker | null>(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  const [base, setBase] = useState<BaseKey>("light");
  const [layersOpen, setLayersOpen] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const layersRef = useDismiss<HTMLDivElement>(layersOpen, () => setLayersOpen(false));

  // create the map once
  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const m = L.map(el, { zoomControl: false, attributionControl: true, preferCanvas: true }).setView([PRISTINA.lat, PRISTINA.lng], 13);
    m.attributionControl.setPrefix(false);
    m.on("click", () => onSelectRef.current(null));
    const sync = () => el.classList.toggle("zoomed-out", m.getZoom() < 15);
    m.on("zoomend", sync);
    sync();
    pins.current = L.layerGroup().addTo(m);
    map.current = m;
    const ro = new ResizeObserver(() => m.invalidateSize());
    ro.observe(el);
    const live = markers.current;
    return () => {
      ro.disconnect();
      m.remove();
      map.current = null;
      tiles.current = null;
      live.clear();
    };
  }, []);

  // base layer
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    const b = BASES[base];
    tiles.current?.remove();
    tiles.current = L.tileLayer(b.url, { attribution: b.attribution, subdomains: b.subdomains ?? "abc", maxZoom: 19 }).addTo(m);
    tiles.current.bringToBack();
  }, [base]);

  // pins follow the list
  useEffect(() => {
    const group = pins.current;
    if (!group) return;
    const live = markers.current;
    const wanted = new Set(items.map((l) => l.id));
    for (const [id, mk] of live) {
      if (!wanted.has(id)) {
        group.removeLayer(mk);
        live.delete(id);
      }
    }
    for (const l of items) {
      if (live.has(l.id)) continue;
      const at = positions.get(l.id);
      if (!at) continue;
      const mk = L.marker(at, { icon: pinIcon(l), keyboard: false });
      mk.on("click", (e) => {
        L.DomEvent.stopPropagation(e);
        onSelectRef.current(l.id);
      });
      group.addLayer(mk);
      live.set(l.id, mk);
    }
  }, [items, positions]);

  // selected / hovered styling (runs after the pins effect so fresh markers get it too)
  useEffect(() => {
    for (const [id, mk] of markers.current) {
      const el = mk.getElement();
      const sel = id === selectedId;
      const hov = id === hoveredId;
      el?.classList.toggle("is-selected", sel);
      el?.classList.toggle("is-hover", hov);
      mk.setZIndexOffset(sel ? 2000 : hov ? 1000 : 0);
    }
  }, [items, selectedId, hoveredId]);

  // re-fit when the result set changes
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    const pts = items.map((l) => positions.get(l.id)).filter((p): p is LatLng => !!p);
    if (!pts.length) return;
    m.invalidateSize();
    m.fitBounds(L.latLngBounds(pts), { padding: [70, 70], maxZoom: 16, animate: false });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fitKey]);

  // bring a newly selected listing into view
  useEffect(() => {
    const m = map.current;
    const at = selectedId ? positions.get(selectedId) : null;
    if (!m || !at) return;
    m.setView(at, Math.max(m.getZoom(), 15), { animate: true });
  }, [selectedId, positions]);

  // let the container settle, then resize (expand toggles change the width)
  useEffect(() => {
    const t = setTimeout(() => map.current?.invalidateSize(), 60);
    return () => clearTimeout(t);
  }, [expanded]);

  const locate = () => {
    if (!("geolocation" in navigator)) return setNote("Location isn't available in this browser");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const m = map.current;
        if (!m) return;
        const at: L.LatLngTuple = [pos.coords.latitude, pos.coords.longitude];
        me.current?.remove();
        me.current = L.circleMarker(at, { radius: 8, color: "#fff", weight: 3, fillColor: "#2F7BFF", fillOpacity: 1 }).addTo(m);
        m.flyTo(at, Math.max(m.getZoom(), 15));
      },
      () => setNote("Couldn't get your location"),
      { enableHighAccuracy: false, timeout: 8000 },
    );
  };

  useEffect(() => {
    if (!note) return;
    const t = setTimeout(() => setNote(null), 3200);
    return () => clearTimeout(t);
  }, [note]);

  return (
    <div className={`map base-${base}`}>
      <div ref={host} className="map-host" role="application" aria-label="Map of listings by neighbourhood" />

      <div className="map-tl">
        <button className="map-btn" onClick={onToggleExpand} aria-label={expanded ? "Show list" : "Expand map"} title={expanded ? "Show list" : "Expand map"}>
          {expanded ? <IconShrink size={18} /> : <IconExpand size={18} />}
        </button>
      </div>

      <div className="map-tr" ref={layersRef}>
        <button className="map-btn" onClick={() => setLayersOpen((o) => !o)} aria-label="Map style" aria-expanded={layersOpen} title="Map style">
          <IconLayers size={18} />
        </button>
        {layersOpen && (
          <ul className="menu layers-menu" role="menu">
            {(Object.keys(BASES) as BaseKey[]).map((k) => (
              <li key={k} role="none">
                <button
                  role="menuitemradio"
                  aria-checked={k === base}
                  onClick={() => {
                    setBase(k);
                    setLayersOpen(false);
                  }}
                >
                  {BASES[k].label}
                  {k === base && <IconCheck size={16} />}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="map-br">
        <button className="map-btn" onClick={locate} aria-label="Find my location" title="Find my location">
          <IconLocate size={18} />
        </button>
        <div className="zoom">
          <button className="map-btn" onClick={() => map.current?.zoomIn()} aria-label="Zoom in">
            <IconPlus size={18} />
          </button>
          <button className="map-btn" onClick={() => map.current?.zoomOut()} aria-label="Zoom out">
            <IconMinus size={18} />
          </button>
        </div>
      </div>

      <p className="map-hint">Pins show the lagje, not the exact address</p>
      {note && (
        <div className="map-note" role="status">
          {note}
        </div>
      )}
      {children}
    </div>
  );
}
