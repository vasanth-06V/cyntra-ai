import { useId } from "react";

/**
 * Brand mark: a "C" (Cyntra) that opens around a four-point spark (the AI),
 * on a rounded tile that runs indigo to violet to pink-violet.
 */
export function LogoMark({ size = 32, className = "" }: { size?: number; className?: string }) {
  const id = useId();
  const tile = `${id}-tile`;
  const shine = `${id}-shine`;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      aria-hidden="true"
      focusable="false"
      className={className}
    >
      <defs>
        <linearGradient id={tile} x1="3" y1="2" x2="29" y2="30" gradientUnits="userSpaceOnUse">
          <stop stopColor="#4f46e5" />
          <stop offset="0.55" stopColor="#7c3aed" />
          <stop offset="1" stopColor="#c026d3" />
        </linearGradient>
        <linearGradient id={shine} x1="16" y1="0" x2="16" y2="18" gradientUnits="userSpaceOnUse">
          <stop stopColor="#fff" stopOpacity="0.28" />
          <stop offset="1" stopColor="#fff" stopOpacity="0" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="9" fill={`url(#${tile})`} />
      <rect width="32" height="32" rx="9" fill={`url(#${shine})`} />
      <path
        d="M19.640 9.870A8 8 0 1 0 19.640 22.130"
        fill="none"
        stroke="#fff"
        strokeWidth="3"
        strokeLinecap="round"
      />
      <path
        d="M23 11.500C23.400 14.300 24.700 15.600 27.500 16C24.700 16.400 23.400 17.700 23 20.500C22.600 17.700 21.300 16.400 18.500 16C21.300 15.600 22.600 14.300 23 11.500Z"
        fill="#fff"
      />
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
