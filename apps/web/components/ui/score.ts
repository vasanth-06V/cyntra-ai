/** Shared score-to-colour mapping so every score in the app reads the same way. */
export type ScoreTone = "success" | "warning" | "danger";

export function scoreTone(fraction: number): ScoreTone {
  if (fraction >= 0.75) return "success";
  if (fraction >= 0.5) return "warning";
  return "danger";
}

export const toneText: Record<ScoreTone, string> = {
  success: "text-success",
  warning: "text-warning",
  danger: "text-destructive",
};

export const toneFill: Record<ScoreTone, string> = {
  success: "bg-success-fill",
  warning: "bg-warning-fill",
  danger: "bg-danger-fill",
};

/** Stroke colour for rings (graphics, so the brighter fill tokens). */
export const toneStroke: Record<ScoreTone, string> = {
  success: "text-success-fill",
  warning: "text-warning-fill",
  danger: "text-danger-fill",
};
