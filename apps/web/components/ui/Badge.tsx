import type { HTMLAttributes } from "react";

export type Tone = "neutral" | "brand" | "success" | "warning" | "danger" | "info";

const tones: Record<Tone, string> = {
  neutral: "bg-secondary text-muted-foreground border-border",
  brand: "bg-accent text-accent-foreground border-primary/20",
  success: "bg-success-soft text-success border-success/25",
  warning: "bg-warning-soft text-warning border-warning/25",
  danger: "bg-destructive-soft text-destructive border-destructive/25",
  info: "bg-info-soft text-info border-info/25",
};

/** Small status pill. Colour is never the only signal: always include text. */
export function Badge({
  tone = "neutral",
  className = "",
  ...props
}: HTMLAttributes<HTMLSpanElement> & { tone?: Tone }) {
  return (
    <span
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-medium ${tones[tone]} ${className}`}
      {...props}
    />
  );
}
