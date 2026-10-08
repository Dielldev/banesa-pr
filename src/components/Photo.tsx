import { useState, type ReactNode } from "react";
import type { Listing } from "../types";
import { photoUrl, spriteStyle } from "../lib/photo";

interface Props {
  listing: Listing;
  width?: 480 | 960;
  className?: string;
  eager?: boolean;
  children?: ReactNode;
}

/** Sprite cell paints instantly; the sharp photo fades in over it, and failure just leaves the sprite. */
export function Photo({ listing, width = 480, className = "", eager = false, children }: Props) {
  const url = photoUrl(listing, width);
  const [state, setState] = useState<"loading" | "ok" | "fail">("loading");
  return (
    <div className={`photo ${className}`} style={spriteStyle(listing.sp)}>
      {url && state !== "fail" && (
        <img
          src={url}
          alt=""
          loading={eager ? "eager" : "lazy"}
          decoding="async"
          referrerPolicy="no-referrer"
          className={state === "ok" ? "in" : ""}
          onLoad={() => setState("ok")}
          onError={() => setState("fail")}
        />
      )}
      {children}
    </div>
  );
}
