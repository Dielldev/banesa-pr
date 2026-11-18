export type Feature =
  | "parking" | "elevator" | "new_build" | "balcony" | "renovated"
  | "basement" | "furnished" | "duplex" | "heating";

export interface ScoreParts {
  value?: number;
  features?: number;
  freshness?: number;
  seller?: number;
  priority?: number;
}

/** One ranked ad, as written by scraper/build_site.py. Missing facts are absent, never null. */
export interface Listing {
  id: string;
  source: string;
  url: string;
  title: string;
  image?: string;
  /** sprite-sheet cell: [sheet, col, row] — the low-res placeholder photo */
  sp?: [number, number, number];
  price?: number;
  price_derived?: boolean;
  /** previous asking price, present when the ad's price was cut in the last 60 days */
  price_was?: number;
  /** day the scraper first saw the ad (YYYY-MM-DD) */
  first_seen?: string;
  area?: number;
  area_uncertain?: boolean;
  rooms?: number;
  floor?: number;
  hood?: string;
  tier?: "core" | "nearby";
  agency?: string;
  seller_type?: "company" | "private";
  phone?: string;
  prio?: 1;
  date?: string;
  days_old?: number;
  eur_m2?: number;
  hood_median_eur_m2?: number;
  discount_pct?: number;
  score?: number;
  score_reason?: string;
  score_parts?: ScoreParts;
  features?: Feature[];
  description?: string;
}

export interface Dataset {
  generated: string;
  /** when the listings last changed; absent in older snapshots */
  updated?: string;
  source: string;
  stats: { total: number; priced: number; core: number; priority?: number };
  listings: Listing[];
}

export type SortKey = "score" | "new" | "price" | "priced" | "ppm" | "area";
export type SegmentKey = "all" | "prio" | "saved";
export type TierKey = "all" | "core" | "nearby";

export interface Filters {
  q: string;
  segment: SegmentKey;
  tier: TierKey;
  hoods: string[];
  rooms: number[];
  feats: Feature[];
  agency: string;
  pmin: number;
  pmax: number;
  amin: number | null;
  amax: number | null;
  /** inclusive ISO dates */
  from: string | null;
  to: string | null;
  preset: string | null;
  undated: boolean;
  sort: SortKey;
}
