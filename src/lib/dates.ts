import type { Dataset, Listing } from "../types";

const DAY = 864e5;

const pad = (n: number) => String(n).padStart(2, "0");
export const isoOf = (d: Date): string => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

/** "Last 7 days" is measured from the crawl, not the reader's clock, so it keeps meaning the same week. */
export function makeClock(generated: string) {
  const crawl = new Date(generated);
  const today = new Date(crawl.getFullYear(), crawl.getMonth(), crawl.getDate());
  const daysBack = (n: number) => {
    const d = new Date(today);
    d.setDate(d.getDate() - n);
    return isoOf(d);
  };
  const daysSince = (iso: string) => Math.round((today.getTime() - Date.parse(iso + "T00:00:00")) / DAY);
  return { today, todayIso: isoOf(today), daysBack, daysSince };
}
export type Clock = ReturnType<typeof makeClock>;

export function agoText(days: number): string {
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 30) return `${days} days ago`;
  if (days < 365) {
    const m = Math.round(days / 30);
    return m === 1 ? "a month ago" : `${m} months ago`;
  }
  const y = Math.floor(days / 365);
  return y === 1 ? "a year ago" : `${y} years ago`;
}

export const shortAgo = (days: number): string =>
  days <= 0 ? "today" : days === 1 ? "1d ago" : days < 30 ? `${days}d ago` : days < 365 ? `${Math.round(days / 30)}mo ago` : `${Math.floor(days / 365)}y ago`;

export const dateText = (iso: string): string =>
  new Date(iso + "T00:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });

export interface DatePreset {
  key: string;
  label: string;
  from: string;
  to: string | null;
}

export function datePresets(listings: Listing[], clock: Clock): DatePreset[] {
  const thisYear = String(clock.today.getFullYear());
  const years = [...new Set(listings.map((l) => l.date?.slice(0, 4)).filter((y): y is string => !!y))].sort().reverse();
  return [
    { key: "7", label: "Last 7 days", from: clock.daysBack(7), to: null },
    { key: "30", label: "Last 30 days", from: clock.daysBack(30), to: null },
    { key: "90", label: "Last 3 months", from: clock.daysBack(90), to: null },
    ...years.map((y) => ({
      key: "y" + y,
      label: y === thisYear ? `This year` : y,
      from: `${y}-01-01`,
      to: `${y}-12-31`,
    })),
  ];
}

export const generatedLabel = (d: Dataset): string =>
  new Date(d.generated).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
