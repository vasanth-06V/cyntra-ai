import type { HTMLAttributes } from "react";

type CardProps = HTMLAttributes<HTMLDivElement> & {
  /** Adds a hover lift and border highlight; use when the whole card is a link. */
  interactive?: boolean;
  /** "raised" gives a stronger shadow for floating surfaces; "tinted" a brand wash. */
  tone?: "default" | "raised" | "tinted";
};

const tones = {
  default: "bg-card shadow-sm",
  raised: "bg-card shadow-md",
  tinted: "bg-accent/60 shadow-xs",
};

export function Card({ className = "", interactive = false, tone = "default", ...props }: CardProps) {
  return (
    <div
      className={`rounded-xl border border-border text-card-foreground ${tones[tone]} ${
        interactive
          ? "transition-[transform,box-shadow,border-color] duration-200 ease-out hover:-translate-y-0.5 hover:border-border-strong hover:shadow-md motion-reduce:hover:translate-y-0"
          : ""
      } ${className}`}
      {...props}
    />
  );
}
