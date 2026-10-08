import type { Listing } from "../types";
import { eur } from "../lib/format";
import { Photo } from "./Photo";
import { IconArea, IconBed, IconClose, IconHeart, IconStairs } from "./Icons";
import { bedsText, priceText } from "./ListingCard";

interface Props {
  listing: Listing;
  saved: boolean;
  onOpen: (id: string) => void;
  onToggleSave: (id: string) => void;
  onClose: () => void;
}

export function MapPopup({ listing: l, saved, onOpen, onToggleSave, onClose }: Props) {
  const beds = bedsText(l);
  return (
    <div className="popup" role="dialog" aria-label={`Selected listing: ${l.title}`}>
      <button className="popup-main" onClick={() => onOpen(l.id)}>
        <Photo key={l.id} listing={l} className="popup-img" />
        <span className="popup-body">
          <span className="status">
            <i />
            For sale
          </span>
          <strong className="popup-price">{priceText(l)}</strong>
          <span className="popup-specs">
            {beds && (
              <span>
                <IconBed size={14} />
                {beds}
              </span>
            )}
            {l.floor != null && (
              <span>
                <IconStairs size={14} />
                Floor {l.floor}
              </span>
            )}
            {l.area != null && (
              <span>
                <IconArea size={14} />
                {l.area} m²
              </span>
            )}
          </span>
          <span className="popup-addr">
            {l.hood ?? "Prishtinë"}, Prishtinë{l.eur_m2 ? ` · ${eur(l.eur_m2)}/m²` : ""}
          </span>
        </span>
      </button>
      <div className="popup-actions">
        <button
          className={`round-btn${saved ? " on" : ""}`}
          aria-label={saved ? "Remove from saved" : "Save listing"}
          aria-pressed={saved}
          onClick={() => onToggleSave(l.id)}
        >
          <IconHeart size={16} filled={saved} />
        </button>
        <button className="round-btn ghost" aria-label="Close" onClick={onClose}>
          <IconClose size={15} />
        </button>
      </div>
    </div>
  );
}
