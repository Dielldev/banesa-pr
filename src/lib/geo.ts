import type { Listing } from "../types";
import { hash } from "./format";

/**
 * The ads carry no coordinates, only a lagje. Each pin is therefore placed inside its
 * lagje (centres from OpenStreetMap, spread on a sunflower spiral so pins don't stack).
 * It shows *which neighbourhood*, never an exact address.
 */
export const HOOD_CENTRES: Record<string, { lat: number; lng: number; r: number }> = {
  "Prishtina e Re": { lat: 42.6379, lng: 21.1679, r: 900 },
  "Mati 1": { lat: 42.649, lng: 21.176, r: 650 },
  "Arbëria": { lat: 42.6619, lng: 21.1501, r: 900 },
  "Qendër": { lat: 42.6604, lng: 21.1606, r: 450 },
  "Bregu i Diellit": { lat: 42.65, lng: 21.1688, r: 600 },
  "Ulpiana": { lat: 42.6504, lng: 21.1607, r: 450 },
  "Tophane": { lat: 42.6682, lng: 21.1606, r: 450 },
  "Dardania": { lat: 42.6575, lng: 21.1445, r: 600 },
  "Lakrishte": { lat: 42.656, lng: 21.1517, r: 450 },
  "Pejton": { lat: 42.6577, lng: 21.1574, r: 300 },
  "Qafa": { lat: 42.6648, lng: 21.1596, r: 300 },
};
export const PRISTINA = { lat: 42.6629, lng: 21.1655 };

const GOLDEN = Math.PI * (3 - Math.sqrt(5));
const M_LAT = 1 / 111_320;

export type LatLng = [number, number];

/** Stable position for every listing, independent of filters. */
export function placeListings(listings: Listing[]): Map<string, LatLng> {
  // rank within the lagje by id hash, so any subset (e.g. the top 24) is spread over the whole lagje
  const byHood = new Map<string, Listing[]>();
  for (const l of listings) {
    const k = l.hood ?? "";
    const g = byHood.get(k);
    if (g) g.push(l);
    else byHood.set(k, [l]);
  }
  const out = new Map<string, LatLng>();
  for (const [key, group] of byHood) {
    const c = HOOD_CENTRES[key] ?? { ...PRISTINA, r: 1200 };
    const n = group.length;
    group.sort((a, b) => hash(a.id) - hash(b.id));
    group.forEach((l, i) => {
      // sunflower: radius ~ sqrt(rank), so density is even across the lagje
      const rad = c.r * Math.sqrt((i + 0.5) / n);
      const ang = i * GOLDEN;
      const dLat = Math.sin(ang) * rad * M_LAT;
      const dLng = (Math.cos(ang) * rad * M_LAT) / Math.cos((c.lat * Math.PI) / 180);
      out.set(l.id, [c.lat + dLat, c.lng + dLng]);
    });
  }
  return out;
}
