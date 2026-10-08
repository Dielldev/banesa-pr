export const eur = (n: number): string => "€" + Math.round(n).toLocaleString("en-US");

export const initials = (name: string): string =>
  name
    .replace(/\b(l\.?l\.?c\.?|n\.?sh\.?|real estate|patundshmeri)\b/gi, "")
    .split(/[\s.]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]!.toUpperCase())
    .join("") || name.slice(0, 2).toUpperCase();

/** stable 0..n-1 bucket for a string */
export function hash(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

export const AVATAR_COLORS = ["#0969da", "#1a7f37", "#8250df", "#bf8700", "#cf222e", "#0e7490", "#bf3989"];
export const avatarColor = (name: string): string => AVATAR_COLORS[hash(name) % AVATAR_COLORS.length]!;
