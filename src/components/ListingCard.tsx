import { memo, type KeyboardEvent, type MouseEvent } from "react";
import type { Listing } from "../types";
import { eur } from "../lib/format";
import { shortAgo } from "../lib/dates";
import { Photo } from "./Photo";
import { Avatar } from "./Avatar";
import { IconArea, IconBed, IconHeart, IconMap, IconPhone, IconStairs, IconStar, IconVerified } from "./Icons";

interface Props {
  listing: Listing;
  saved: boolean;
  active: boolean;
  daysOld: number | null;
  onOpen: (id: string) => void;
  onToggleSave: (id: string) => void;
  onShowOnMap: (id: string) => void;
  onHover: (id: string | null) => void;
}

export const priceText = (l: Listing): string =>
  l.price ? (l.price_derived ? "~" : "") + eur(l.price) : "Price on ask";

export const bedsText = (l: Listing): string | null =>
  l.rooms == null ? null : l.rooms === 0 ? "Studio" : `${l.rooms} bed`;

function CardImpl({ listing: l, saved, active, daysOld, onOpen, onToggleSave, onShowOnMap, onHover }: Props) {
  const stop = (fn: () => void) => (e: MouseEvent) => {
    e.stopPropagation();
    fn();
  };
  const onKey = (e: KeyboardEvent) => {
    if (e.target === e.currentTarget && (e.key === "Enter" || e.key === " ")) {
      e.preventDefault();
      onOpen(l.id);
    }
  };
  const seller = l.agency ?? (l.seller_type === "private" ? "Private seller" : l.source);
  const beds = bedsText(l);
  const below = l.discount_pct != null && l.discount_pct >= 5;

  return (
    <article
      className={`card${active ? " is-active" : ""}`}
      tabIndex={0}
      aria-label={`${l.title}, ${priceText(l)}`}
      onClick={() => onOpen(l.id)}
      onKeyDown={onKey}
      onMouseEnter={() => onHover(l.id)}
      onMouseLeave={() => onHover(null)}
      data-id={l.id}
    >
      <Photo listing={l} className="card-img">
        {l.score != null && (
          <span className="card-badge" title="Value score out of 100">
            <IconStar size={14} filled />
            {Math.round(l.score)}
          </span>
        )}
        <div className="agent">
          <Avatar name={seller} size={36} />
          <div className="agent-txt">
            <span className="agent-name">
              <span>{seller}</span>
              {l.seller_type === "company" && <IconVerified size={14} />}
            </span>
            <span className="agent-sub">
              {l.phone ? (
                <>
                  <IconPhone size={12} />
                  {l.phone}
                </>
              ) : (
                `via ${l.source}`
              )}
            </span>
          </div>
        </div>
      </Photo>

      <div className="card-row">
        <span className="status">
          <i />
          For sale
        </span>
        <div className="round-btns">
          <button className="round-btn" aria-label="Show on map" title="Show on map" onClick={stop(() => onShowOnMap(l.id))}>
            <IconMap size={15} />
          </button>
          <button
            className={`round-btn${saved ? " on" : ""}`}
            aria-label={saved ? "Remove from saved" : "Save listing"}
            aria-pressed={saved}
            onClick={stop(() => onToggleSave(l.id))}
          >
            <IconHeart size={15} filled={saved} />
          </button>
        </div>
      </div>

      <div className="card-price">
        <strong>{priceText(l)}</strong>
        {below && (
          <span className="chip-good" title={l.score_reason}>
            {Math.round(l.discount_pct!)}% below median
          </span>
        )}
      </div>

      <ul className="specs">
        {beds && (
          <li>
            <IconBed size={15} />
            <b>{beds}</b>
          </li>
        )}
        {l.floor != null && (
          <li>
            <IconStairs size={15} />
            <b>Floor {l.floor}</b>
          </li>
        )}
        {l.area != null && (
          <li>
            <IconArea size={15} />
            <b>{l.area} m²</b>
          </li>
        )}
      </ul>

      <p className="addr">
        {l.hood ?? "Prishtinë"}, Prishtinë{l.eur_m2 ? ` · ${eur(l.eur_m2)}/m²` : ""}
      </p>
      <p className="listed">
        Listed by {seller}
        {daysOld != null ? ` · ${shortAgo(daysOld)}` : ""}
      </p>
    </article>
  );
}

export const ListingCard = memo(CardImpl);
