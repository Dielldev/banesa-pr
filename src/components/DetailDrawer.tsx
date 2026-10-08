import { useEffect, useRef, useState } from "react";
import type { Listing } from "../types";
import { eur } from "../lib/format";
import { FEATURE_LABELS } from "../lib/filters";
import { agoText, dateText } from "../lib/dates";
import { useScrollLock } from "../lib/hooks";
import { Photo } from "./Photo";
import { Avatar } from "./Avatar";
import { bedsText, priceText } from "./ListingCard";
import { IconArea, IconBed, IconCalendar, IconCheck, IconClose, IconExternal, IconHeart, IconPhone, IconPin, IconStairs, IconStar, IconVerified } from "./Icons";

type Tab = "overview" | "value" | "details";

const PART_LABELS: Record<string, [string, number]> = {
  value: ["Price vs lagje", 70],
  features: ["Build & amenities", 16],
  freshness: ["Freshness", 6],
  seller: ["Verified seller", 3],
  priority: ["Priority agency", 5],
};

interface Props {
  listing: Listing;
  saved: boolean;
  daysOld: number | null;
  onToggleSave: (id: string) => void;
  onClose: () => void;
}

export function DetailDrawer({ listing: l, saved, daysOld, onToggleSave, onClose }: Props) {
  const [tab, setTab] = useState<Tab>("overview");
  const closeRef = useRef<HTMLButtonElement>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  useScrollLock(true);

  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();
    const key = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("keydown", key);
      opener?.focus?.();
    };
  }, [onClose]);

  useEffect(() => {
    setTab("overview");
    bodyRef.current?.scrollTo({ top: 0 });
  }, [l.id]);

  const seller = l.agency ?? (l.seller_type === "private" ? "Private seller" : l.source);
  const beds = bedsText(l);
  const fresh = daysOld != null && daysOld <= 7;

  return (
    <div className="overlay drawer-overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <aside className="drawer" role="dialog" aria-modal="true" aria-label={l.title}>
        <div className="drawer-scroll" ref={bodyRef}>
          <Photo key={l.id} listing={l} width={960} eager className="drawer-img">
            <button ref={closeRef} className="round-btn float-close" onClick={onClose} aria-label="Close details">
              <IconClose size={16} />
            </button>
            {l.score != null && (
              <span className="card-badge big">
                <IconStar size={15} filled />
                {Math.round(l.score)} / 100
              </span>
            )}
          </Photo>

          <div className="drawer-pad">
            <div className="drawer-top">
              <div>
                <span className="status">
                  <i />
                  For sale{l.prio ? " · Priority agency" : ""}
                </span>
                <h2>{l.title}</h2>
              </div>
              <div className="drawer-price">
                <strong>{priceText(l)}</strong>
                {l.eur_m2 && <small>{eur(l.eur_m2)} / m²</small>}
              </div>
            </div>

            <p className="drawer-loc">
              <IconPin size={15} />
              {l.hood ?? "Prishtinë"}, Prishtinë
            </p>
            <p className={`drawer-loc${fresh ? " fresh" : ""}`}>
              <IconCalendar size={15} />
              {l.date && daysOld != null ? `Published ${dateText(l.date)} · ${agoText(daysOld)}` : "Publication date not stated"}
            </p>

            <ul className="specs big">
              {beds && (
                <li>
                  <IconBed size={17} />
                  <b>{beds}</b>
                </li>
              )}
              {l.floor != null && (
                <li>
                  <IconStairs size={17} />
                  <b>Floor {l.floor}</b>
                </li>
              )}
              {l.area != null && (
                <li>
                  <IconArea size={17} />
                  <b>{l.area} m²</b>
                </li>
              )}
            </ul>

            <div className="seller">
              <Avatar name={seller} size={44} />
              <div>
                <span className="agent-name">
                  <span>{seller}</span>
                  {l.seller_type === "company" && <IconVerified size={15} />}
                </span>
                <span className="agent-sub">{l.phone ?? `via ${l.source}`}</span>
              </div>
              {l.phone && (
                <a className="round-btn call" href={`tel:${l.phone.replace(/\s/g, "")}`} aria-label={`Call ${l.phone}`}>
                  <IconPhone size={16} />
                </a>
              )}
            </div>

            <div className="tabs" role="tablist">
              {(["overview", "value", "details"] as Tab[]).map((t) => (
                <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}>
                  {t === "overview" ? "Overview" : t === "value" ? "Value breakdown" : "Details"}
                </button>
              ))}
            </div>

            <div className="tabpane" role="tabpanel">
              {tab === "overview" && (
                <>
                  <p className="body">{l.description || "This ad has no description text."}</p>
                  {!!l.features?.length && (
                    <ul className="feat-list">
                      {l.features.map((k) => (
                        <li key={k}>
                          <IconCheck size={14} />
                          {FEATURE_LABELS[k] ?? k}
                        </li>
                      ))}
                    </ul>
                  )}
                </>
              )}
              {tab === "value" && <ValuePane l={l} />}
              {tab === "details" && (
                <dl className="kv">
                  {[
                    ["Agency", seller],
                    ["Lagjja", l.hood ?? "—"],
                    ["Asking price", l.price ? (l.price_derived ? `~${eur(l.price)} (from €/m²)` : eur(l.price)) : "On ask"],
                    ["Price per m²", l.eur_m2 ? eur(l.eur_m2) : "—"],
                    ["Surface", l.area ? `${l.area} m²${l.area_uncertain ? " · ambiguous in the ad" : ""}` : "not stated"],
                    ["Published", l.date ? `${dateText(l.date)}${daysOld != null ? ` · ${agoText(daysOld)}` : ""}` : "not stated in the ad"],
                    ["Value score", l.score != null ? `${l.score} / 100` : "not scored"],
                    ["Source", l.source],
                  ].map(([k, v]) => (
                    <div key={k}>
                      <dt>{k}</dt>
                      <dd>{v}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </div>
          </div>
        </div>

        <footer className="drawer-foot">
          <button className={`btn-outline${saved ? " on" : ""}`} aria-pressed={saved} onClick={() => onToggleSave(l.id)}>
            <IconHeart size={17} filled={saved} />
            {saved ? "Saved" : "Save"}
          </button>
          <a className="btn-primary" href={l.url} target="_blank" rel="noopener noreferrer">
            Open the ad
            <IconExternal size={16} />
          </a>
        </footer>
      </aside>
    </div>
  );
}

function ValuePane({ l }: { l: Listing }) {
  if (l.eur_m2 == null) {
    return <p className="body">This ad gives no price or no size, so it can't be valued against its lagje median.</p>;
  }
  const med = l.hood_median_eur_m2 ?? l.eur_m2;
  const top = Math.max(l.eur_m2, med) * 1.25;
  const tone = (l.discount_pct ?? 0) >= 7 ? "good" : (l.discount_pct ?? 0) <= -7 ? "bad" : "mid";
  const parts = Object.entries(PART_LABELS).filter(([k]) => (l.score_parts as Record<string, number | undefined> | undefined)?.[k] != null);
  return (
    <>
      <div className="vbar-row">
        <span>
          This flat · <b>{eur(l.eur_m2)}/m²</b>
        </span>
        <span>
          {l.hood ?? "Area"} median · {eur(med)}/m²
        </span>
      </div>
      <div className="vbar" aria-hidden="true">
        <div className={`vbar-fill ${tone}`} style={{ width: `${(l.eur_m2 / top) * 100}%` }} />
        <div className="vbar-med" style={{ left: `${(med / top) * 100}%` }} />
      </div>
      {l.score_reason && <p className="body">{l.score_reason}</p>}
      <div className="parts">
        {parts.map(([k, [label, max]]) => {
          const v = (l.score_parts as Record<string, number>)[k]!;
          return (
            <div className="part" key={k}>
              <span>{label}</span>
              <span className="part-bar">
                <i style={{ width: `${Math.max(3, (v / max) * 100)}%` }} />
              </span>
              <b>{v}</b>
            </div>
          );
        })}
      </div>
    </>
  );
}
