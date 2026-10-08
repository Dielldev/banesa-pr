import type { Listing } from "../types";

const COLS = 10;
const ROWS = 8;

/** MerrJep serves any size from the same path; the scrape stored the 200×160 thumbnail. */
export function photoUrl(l: Listing, width: 480 | 960 = 480): string | null {
  if (!l.image) return null;
  if (l.image.includes("media.merrjep.com")) {
    const h = Math.round(width * 0.75);
    return l.image.replace("/200/160/", `/${width}/${h}/`);
  }
  return l.image;
}

/** Sprite cell as inline CSS — a blurry-but-instant placeholder under the real photo. */
export function spriteStyle(sp: Listing["sp"]): React.CSSProperties {
  if (!sp) return {};
  return {
    backgroundImage: `url(/sprites/s${sp[0]}.jpg)`,
    backgroundSize: `${COLS * 100}% ${ROWS * 100}%`,
    backgroundPosition: `${(sp[1] * 100) / (COLS - 1)}% ${(sp[2] * 100) / (ROWS - 1)}%`,
  };
}
