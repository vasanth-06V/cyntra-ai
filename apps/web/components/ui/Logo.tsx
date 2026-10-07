import { useId } from "react";

/**
 * Brand mark ("Meter C"): three nested arcs that read as a C and as a score
 * gauge, with one fuchsia dot in the opening for the AI. Indigo-to-violet gradient, no tile,
 * so it sits on light and dark surfaces alike.
 */
export function LogoMark({ size = 32, className = "" }: { size?: number; className?: string }) {
  const id = useId();
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      aria-hidden="true"
      focusable="false"
      className={className}
    >
      <defs>
        <linearGradient id={id} x1="6" y1="8" x2="54" y2="56" gradientUnits="userSpaceOnUse">
          <stop stopColor="#4f46e5" />
          <stop offset="1" stopColor="#a78bfa" />
        </linearGradient>
      </defs>
      <g fill="none" stroke={`url(#${id})`} strokeWidth="5.4" strokeLinecap="round">
        <path opacity="0.42" d="M45.43 13.62A24 24 0 1 0 45.43 50.38" />
        <path opacity="0.72" d="M40.61 19.36A16.5 16.5 0 1 0 40.61 44.64" />
        <path d="M35.78 25.11A9 9 0 1 0 35.78 38.89" />
      </g>
      <circle cx="48" cy="32" r="3.4" fill="#c026d3" />
    </svg>
  );
}

export function Logo({
  className = "",
  size = 30,
  showWordmark = true,
}: {
  className?: string;
  size?: number;
  showWordmark?: boolean;
}) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <LogoMark size={size} />
      {showWordmark && (
        <span className="text-[17px] font-semibold tracking-[-0.03em]">
          Cyntra<span className="text-primary">AI</span>
        </span>
      )}
    </span>
  );
}
