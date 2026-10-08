import { useCallback, useState } from "react";
import type { Listing, SegmentKey } from "../types";
import { useDismiss } from "../lib/hooks";
import { shortAgo } from "../lib/dates";
import { Avatar } from "./Avatar";
import { priceText } from "./ListingCard";
import { IconBell, IconBuilding, IconChevron, IconHeart, IconShare, IconStar, LogoMark } from "./Icons";

interface Props {
  segment: SegmentKey;
  counts: Record<SegmentKey, number>;
  onSegment: (s: SegmentKey) => void;
  onShare: () => void;
  newest: { listing: Listing; days: number }[];
  asOf: string;
  total: number;
  savedCount: number;
  onOpen: (id: string) => void;
  onShowSaved: () => void;
  onClearSaved: () => void;
}

const SEGMENTS: { key: SegmentKey; label: string; icon: typeof IconBuilding }[] = [
  { key: "all", label: "Apartments", icon: IconBuilding },
  { key: "prio", label: "Priority", icon: IconStar },
  { key: "saved", label: "Saved", icon: IconHeart },
];

export function Header({ segment, counts, onSegment, onShare, newest, asOf, total, savedCount, onOpen, onShowSaved, onClearSaved }: Props) {
  const [bell, setBell] = useState(false);
  const [user, setUser] = useState(false);
  const closeBell = useCallback(() => setBell(false), []);
  const closeUser = useCallback(() => setUser(false), []);
  const bellRef = useDismiss<HTMLDivElement>(bell, closeBell);
  const userRef = useDismiss<HTMLDivElement>(user, closeUser);

  return (
    <header className="header">
      <a className="logo" href="/" aria-label="Banesa home">
        <LogoMark size={30} />
        <span>Banesa</span>
      </a>

      <nav className="segments" aria-label="Listing groups">
        {SEGMENTS.map(({ key, label, icon: Icon }) => (
          <button key={key} className="segment" aria-pressed={segment === key} onClick={() => onSegment(key)}>
            <Icon size={19} />
            <span>{label}</span>
            <em>{counts[key].toLocaleString("en-US")}</em>
          </button>
        ))}
      </nav>

      <div className="header-right">
        <button className="outline-btn" onClick={onShare} aria-label="Copy a link to this view" title="Copy a link to this view">
          <IconShare size={19} />
        </button>

        <div className="pop-anchor" ref={bellRef}>
          <button className="outline-btn" onClick={() => setBell((o) => !o)} aria-label="Newest listings" aria-expanded={bell} title="Newest listings">
            <IconBell size={19} />
            {newest.length > 0 && <span className="dot" />}
          </button>
          {bell && (
            <div className="menu panel bell-panel" role="dialog" aria-label="Newest listings">
              <h4>Newest listings</h4>
              <p className="muted">Published in the week up to {asOf}</p>
              <ul>
                {newest.map(({ listing: l, days }) => (
                  <li key={l.id}>
                    <button
                      onClick={() => {
                        setBell(false);
                        onOpen(l.id);
                      }}
                    >
                      <span className="n-title">{l.title}</span>
                      <span className="n-meta">
                        {priceText(l)} · {l.hood ?? "Prishtinë"} · {shortAgo(days)}
                      </span>
                    </button>
                  </li>
                ))}
                {!newest.length && <li className="muted pad">Nothing new in that week.</li>}
              </ul>
            </div>
          )}
        </div>

        <div className="pop-anchor" ref={userRef}>
          <button className="user" onClick={() => setUser((o) => !o)} aria-expanded={user} aria-haspopup="menu">
            <Avatar name="Diell" size={42} />
            <span className="user-txt">
              <b>Diell</b>
              <small>Buying in Pristina</small>
            </span>
            <IconChevron size={16} />
          </button>
          {user && (
            <ul className="menu panel user-menu" role="menu">
              <li role="none">
                <button
                  role="menuitem"
                  onClick={() => {
                    setUser(false);
                    onShowSaved();
                  }}
                >
                  Saved homes <em>{savedCount}</em>
                </button>
              </li>
              <li role="none">
                <button
                  role="menuitem"
                  disabled={!savedCount}
                  onClick={() => {
                    setUser(false);
                    if (window.confirm(`Remove all ${savedCount} saved homes?`)) onClearSaved();
                  }}
                >
                  Clear saved
                </button>
              </li>
              <li className="muted pad" role="none">
                {total.toLocaleString("en-US")} listings · crawled {asOf}
              </li>
            </ul>
          )}
        </div>
      </div>
    </header>
  );
}
