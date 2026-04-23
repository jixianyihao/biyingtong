import type { ReactNode } from 'react';

// Single-file SVG icon registry. Heroicons-ish stroke style, drawn in a 24x24 viewbox.
const icons: Record<string, ReactNode> = {
  dashboard: (
    <>
      <path d="M3 3h8v8H3z" />
      <path d="M13 3h8v8h-8z" />
      <path d="M3 13h8v8H3z" />
      <path d="M13 13h8v8h-8z" />
    </>
  ),
  agent: (
    <>
      <circle cx="12" cy="8" r="3.5" />
      <path d="M5 20c0-4 3-7 7-7s7 3 7 7" />
    </>
  ),
  live: (
    <>
      <path d="M3 12h4l2-7 4 14 2-7h6" />
    </>
  ),
  risk: (
    <>
      <path d="M12 3L3 7v6c0 5 4 9 9 10 5-1 9-5 9-10V7l-9-4z" />
      <path d="M9 12l2 2 4-4" />
    </>
  ),
  filter: (
    <>
      <path d="M4 5h16l-6 8v6l-4-2v-4L4 5z" />
    </>
  ),
  code: (
    <>
      <path d="M8 9l-4 3 4 3M16 9l4 3-4 3M14 5l-4 14" />
    </>
  ),
  backtest: (
    <>
      <path d="M3 3v18h18" />
      <path d="M7 15l4-6 3 3 6-8" />
    </>
  ),
  list: (
    <>
      <path d="M8 6h13" />
      <path d="M8 12h13" />
      <path d="M8 18h13" />
      <circle cx="4" cy="6" r="1" />
      <circle cx="4" cy="12" r="1" />
      <circle cx="4" cy="18" r="1" />
    </>
  ),
  chevron: (
    <>
      <path d="M9 6l6 6-6 6" />
    </>
  ),
};

export function Icon({
  name,
  size = 16,
  className,
}: {
  name: string;
  size?: number;
  className?: string;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      {icons[name] ?? icons.chevron}
    </svg>
  );
}
