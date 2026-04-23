// App logo — ported from static/src/common.jsx::Logo, tweaked for TS.

export function Logo({ size = 24 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none">
      <rect
        x="1"
        y="1"
        width="30"
        height="30"
        rx="6"
        fill="oklch(0.18 0.012 260)"
        stroke="var(--brand)"
        strokeWidth={1.2}
      />
      <path
        d="M10 22 L14 12 L17 18 L22 8"
        stroke="var(--brand)"
        strokeWidth={1.8}
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
      <circle cx="22" cy="8" r="1.8" fill="var(--up)" />
      <line x1="10" y1="25" x2="22" y2="25" stroke="var(--brand)" strokeWidth={1} opacity={0.4} />
    </svg>
  );
}
