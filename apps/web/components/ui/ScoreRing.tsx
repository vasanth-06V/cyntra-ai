import type { ReactNode } from "react";
import { CountUp } from "./CountUp";
import { scoreTone, toneStroke, toneText } from "./score";

/**
 * Circular score gauge. The stroke draws in with a CSS animation (covered by
 * the global reduced-motion rule), the number counts up. `value` is 0-100.
 */
export function ScoreRing({
  value,
  size = 168,
  stroke = 12,
  children,
  className = "",
  animateNumber = true,
  showValue = true,
}: {
  value: number;
  size?: number;
  stroke?: number;
  /** Shown under the number inside the ring. */
  children?: ReactNode;
  className?: string;
  animateNumber?: boolean;
  /** Hide the centre number when the value is printed next to the ring. */
  showValue?: boolean;
}) {
  const clamped = Math.max(0, Math.min(100, value));
  const r = (size - stroke) / 2;
  const circ = 2 * Math.PI * r;
  const tone = scoreTone(clamped / 100);
  const small = size < 96;

  return (
    <div
      className={`relative inline-flex items-center justify-center ${className}`}
      style={{ width: size, height: size }}
    >
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        aria-hidden="true"
        className={`-rotate-90 ${toneStroke[tone]}`}
      >
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--secondary)" strokeWidth={stroke} />
        <circle
          className="ring-stroke"
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="currentColor"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circ}
          strokeDashoffset={circ * (1 - clamped / 100)}
          style={{ ["--ring-circ" as string]: circ }}
        />
      </svg>
      {showValue && (
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
        <span
          className={`font-semibold leading-none tracking-[-0.04em] tabular-nums ${toneText[tone]} ${small ? "text-xl" : "text-5xl"}`}
        >
          {animateNumber ? <CountUp value={clamped} /> : clamped}
        </span>
        {children ? (
          <span className="mt-1 text-xs font-medium text-muted-foreground">{children}</span>
        ) : (
          !small && <span className="mt-1 text-xs font-medium text-muted-foreground">out of 100</span>
        )}
      </div>
      )}
    </div>
  );
}
