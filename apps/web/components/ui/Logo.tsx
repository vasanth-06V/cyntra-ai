import { useId } from "react";

/** Brand mark: a rounded tile with a soft indigo-to-violet gradient and a spark. */
export function LogoMark({ size = 32, className = "" }: { size?: number; className?: string }) {
  const id = useId();
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
        <linearGradient id={id} x1="4" y1="2" x2="28" y2="30" gradientUnits="userSpaceOnUse">
          <stop stopColor="#5b54e8" />
          <stop offset="1" stopColor="#7c3aed" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="9" fill={`url(#${id})`} />
      <path
        d="M21.500 11.200A7 7 0 1 0 21.500 20.800"
        fill="none"
        stroke="#fff"
        strokeWidth="2.600"
        strokeLinecap="round"
      />
      <path d="M22.800 12.500v5M20.300 15h5" stroke="#fff" strokeWidth="2" strokeLinecap="round" opacity="0.9" />
    </svg>
  );
}

export function Logo({ className = "", size = 30 }: { className?: string; size?: number }) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <LogoMark size={size} />
      <span className="text-[17px] font-semibold tracking-[-0.03em]">
        Cyntra<span className="text-primary">AI</span>
      </span>
    </span>
  );
}
