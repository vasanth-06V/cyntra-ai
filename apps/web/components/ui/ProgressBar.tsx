import { scoreTone, toneFill, type ScoreTone } from "./score";

/**
 * Horizontal bar for a 0-1 fraction. Decorative: the value is always printed
 * next to it. The fill grows in with a CSS animation (reduced-motion safe) and
 * keeps its colour when printed.
 */
export function ProgressBar({
  fraction,
  tone,
  className = "",
  height = "h-2",
}: {
  fraction: number;
  tone?: ScoreTone | "brand";
  className?: string;
  height?: string;
}) {
  const f = Math.max(0, Math.min(1, fraction));
  const fill = tone === "brand" ? "bg-primary" : toneFill[tone ?? scoreTone(f)];
  return (
    <div aria-hidden="true" className={`overflow-hidden rounded-full bg-secondary ${height} ${className}`}>
      <div className={`bar-fill h-full rounded-full transition-[width] duration-1000 ease-linear ${fill}`} style={{ width: `${f * 100}%` }} />
    </div>
  );
}
