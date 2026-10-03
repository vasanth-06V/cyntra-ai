import type { ReactNode } from "react";
import { AlertIcon, CheckIcon, InfoIcon } from "./icons";
import type { Tone } from "./Badge";

const styles: Record<"danger" | "success" | "warning" | "info", string> = {
  danger: "border-destructive/30 bg-destructive-soft text-destructive",
  success: "border-success/30 bg-success-soft text-success",
  warning: "border-warning/30 bg-warning-soft text-warning",
  info: "border-info/30 bg-info-soft text-info",
};

/** Inline message with an icon. Pass role="alert" for errors that appear after an action. */
export function Alert({
  tone = "danger",
  children,
  className = "",
  role,
}: {
  tone?: Exclude<Tone, "neutral" | "brand">;
  children: ReactNode;
  className?: string;
  role?: "alert" | "status";
}) {
  const Glyph = tone === "success" ? CheckIcon : tone === "info" ? InfoIcon : AlertIcon;
  return (
    <div
      role={role}
      className={`flex items-start gap-2.5 rounded-lg border px-3.5 py-2.5 text-sm animate-fade-in ${styles[tone]} ${className}`}
    >
      <Glyph size={16} className="mt-0.5 shrink-0" />
      <div className="min-w-0 flex-1 break-words">{children}</div>
    </div>
  );
}
