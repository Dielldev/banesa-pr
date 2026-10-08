import type { ReactNode, SVGProps } from "react";

type P = Omit<SVGProps<SVGSVGElement>, "children"> & { size?: number };

function Svg({ size = 18, children, ...rest }: P & { children: ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      {children}
    </svg>
  );
}

export const LogoMark = ({ size = 28 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
    <defs>
      <linearGradient id="lg" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="#2f8cf0" />
        <stop offset="1" stopColor="#0550ae" />
      </linearGradient>
    </defs>
    <path d="M3 6h12.4L9.2 16.6Z" fill="url(#lg)" />
    <path d="M16.6 6H29l-6.2 10.6Z" fill="url(#lg)" />
    <path d="M9.8 17.4h12.4L16 28Z" fill="url(#lg)" />
  </svg>
);

export const IconBuilding = (p: P) => (
  <Svg {...p}>
    <path d="M4 21V5.5A1.5 1.5 0 0 1 5.5 4h8A1.5 1.5 0 0 1 15 5.5V21" />
    <path d="M15 10h3.5A1.5 1.5 0 0 1 20 11.5V21M2.5 21h19" />
    <path d="M8 8h3M8 12h3M8 16h3" />
  </Svg>
);
export const IconStar = ({ filled, ...p }: P & { filled?: boolean }) => (
  <Svg {...p} fill={filled ? "currentColor" : "none"}>
    <path d="m12 3.2 2.7 5.6 6.1.8-4.5 4.2 1.1 6.1L12 17l-5.4 2.9 1.1-6.1-4.5-4.2 6.1-.8Z" />
  </Svg>
);
export const IconHeart = ({ filled, ...p }: P & { filled?: boolean }) => (
  <Svg {...p} fill={filled ? "currentColor" : "none"}>
    <path d="M12 20.5s-7.5-4.6-9.3-9.4C1.5 7.8 3.4 4.8 6.6 4.8c2 0 3.5 1.1 4.4 2.6.9-1.5 2.4-2.6 4.4-2.6 3.2 0 5.1 3 3.9 6.3-1.8 4.8-7.3 9.4-7.3 9.4Z" />
  </Svg>
);
export const IconShare = (p: P) => (
  <Svg {...p}>
    <path d="M12 15V3.5M7.5 7.5 12 3l4.5 4.5" />
    <path d="M5 12v6.5A1.5 1.5 0 0 0 6.5 20h11a1.5 1.5 0 0 0 1.5-1.5V12" />
  </Svg>
);
export const IconBell = (p: P) => (
  <Svg {...p}>
    <path d="M6 16.5V11a6 6 0 1 1 12 0v5.5l1.5 2h-15Z" />
    <path d="M10 21a2.2 2.2 0 0 0 4 0" />
  </Svg>
);
export const IconChevron = (p: P) => (
  <Svg {...p}>
    <path d="m6 9 6 6 6-6" />
  </Svg>
);
export const IconSearch = (p: P) => (
  <Svg {...p}>
    <circle cx="11" cy="11" r="6.8" />
    <path d="m20 20-3.9-3.9" />
  </Svg>
);
export const IconSliders = (p: P) => (
  <Svg {...p}>
    <path d="M3 7h9M16 7h5M3 17h5M12 17h9" />
    <circle cx="14" cy="7" r="2" />
    <circle cx="10" cy="17" r="2" />
  </Svg>
);
export const IconMap = (p: P) => (
  <Svg {...p}>
    <path d="m3.5 6.5 5.5-2 6 2 5.5-2v13l-5.5 2-6-2-5.5 2Z" />
    <path d="M9 4.5v13M15 6.5v13" />
  </Svg>
);
export const IconGrid = (p: P) => (
  <Svg {...p}>
    <rect x="4" y="4" width="6.5" height="6.5" rx="1.6" />
    <rect x="13.5" y="4" width="6.5" height="6.5" rx="1.6" />
    <rect x="4" y="13.5" width="6.5" height="6.5" rx="1.6" />
    <rect x="13.5" y="13.5" width="6.5" height="6.5" rx="1.6" />
  </Svg>
);
export const IconExpand = (p: P) => (
  <Svg {...p}>
    <path d="M14 4h6v6M10 20H4v-6M20 4l-6.5 6.5M4 20l6.5-6.5" />
  </Svg>
);
export const IconShrink = (p: P) => (
  <Svg {...p}>
    <path d="M20 10h-6V4M4 14h6v6M14 10l6.5-6.5M10 14l-6.5 6.5" />
  </Svg>
);
export const IconLayers = (p: P) => (
  <Svg {...p}>
    <path d="m12 3.5 8.5 4.5-8.5 4.5L3.5 8Z" />
    <path d="m3.5 12.2 8.5 4.5 8.5-4.5M3.5 16.4l8.5 4.5 8.5-4.5" />
  </Svg>
);
export const IconPlus = (p: P) => (
  <Svg {...p}>
    <path d="M12 5v14M5 12h14" />
  </Svg>
);
export const IconMinus = (p: P) => (
  <Svg {...p}>
    <path d="M5 12h14" />
  </Svg>
);
export const IconLocate = (p: P) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="3.2" />
    <circle cx="12" cy="12" r="7.5" />
    <path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22" />
  </Svg>
);
export const IconBed = (p: P) => (
  <Svg {...p}>
    <path d="M3 18.5V6M3 14h18v4.5M21 14v-2.2a2.8 2.8 0 0 0-2.8-2.8H11v5" />
    <circle cx="7" cy="11" r="1.6" />
  </Svg>
);
export const IconStairs = (p: P) => (
  <Svg {...p}>
    <path d="M4 20h4v-4h4v-4h4V8h4" />
    <path d="M4 20h16" />
  </Svg>
);
export const IconArea = (p: P) => (
  <Svg {...p}>
    <path d="M4 4h5M4 4v5M20 20h-5M20 20v-5" />
    <rect x="4" y="4" width="16" height="16" rx="2.4" strokeDasharray="0.1 3.2" />
    <path d="m8.5 15.5 7-7M8.5 15.5h3M8.5 15.5v-3M15.5 8.5h-3M15.5 8.5v3" />
  </Svg>
);
export const IconPhone = (p: P) => (
  <Svg {...p}>
    <path d="M5.2 4h3.3l1.6 4-2.1 1.4a11 11 0 0 0 5.6 5.6l1.4-2.1 4 1.6v3.3a1.7 1.7 0 0 1-1.8 1.7A15.5 15.5 0 0 1 3.5 5.8 1.7 1.7 0 0 1 5.2 4Z" />
  </Svg>
);
export const IconVerified = ({ size = 14 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" aria-label="Verified company" role="img">
    <path
      fill="#2F7BFF"
      d="M12 1.6l2.5 1.9 3.1-.1 1 2.9 2.6 1.8-.9 3 .9 3-2.6 1.8-1 2.9-3.1-.1L12 22.4l-2.5-1.9-3.1.1-1-2.9-2.6-1.8.9-3-.9-3 2.6-1.8 1-2.9 3.1.1Z"
    />
    <path d="m8.2 12.3 2.5 2.5 5-5.2" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);
export const IconClose = (p: P) => (
  <Svg {...p}>
    <path d="M6 6l12 12M18 6 6 18" />
  </Svg>
);
export const IconCheck = (p: P) => (
  <Svg {...p} strokeWidth={2.2}>
    <path d="m5 12.5 4.5 4.5L19 7.5" />
  </Svg>
);
export const IconExternal = (p: P) => (
  <Svg {...p}>
    <path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" />
  </Svg>
);
export const IconCalendar = (p: P) => (
  <Svg {...p}>
    <rect x="3.5" y="5" width="17" height="15.5" rx="2.4" />
    <path d="M8 3v4M16 3v4M3.5 10.5h17" />
  </Svg>
);
export const IconPin = (p: P) => (
  <Svg {...p}>
    <path d="M12 21s7-5.6 7-11a7 7 0 1 0-14 0c0 5.4 7 11 7 11Z" />
    <circle cx="12" cy="10" r="2.5" />
  </Svg>
);
export const IconTrendDown = (p: P) => (
  <Svg {...p}>
    <path d="m3 7 6 6 4-4 8 8M21 11v6h-6" />
  </Svg>
);
