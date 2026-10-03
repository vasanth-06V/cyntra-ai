import { ClockIcon } from "@/components/ui/icons";
import { ProgressBar } from "@/components/ui/ProgressBar";

/**
 * Current phase plus time left. The timer is a role="timer" (not a live
 * region), so screen readers are not interrupted every second.
 */
export function PhaseTimer({
  phase,
  minutesRemaining,
  totalMinutes = 60,
}: {
  phase: string;
  minutesRemaining: number;
  totalMinutes?: number;
}) {
  const mins = Math.floor(minutesRemaining);
  const secs = Math.max(0, Math.round((minutesRemaining - mins) * 60));
  const low = minutesRemaining <= 5;
  const elapsed = Math.max(0, Math.min(1, 1 - minutesRemaining / totalMinutes));

  return (
    <div className="flex min-w-0 items-center gap-3 sm:gap-4">
      <div className="min-w-0">
        <span className="block text-[11px] font-medium uppercase tracking-[0.08em] text-muted-foreground">
          Phase
        </span>
        <span className="block truncate text-sm font-semibold capitalize">{phase.replace(/_/g, " ")}</span>
      </div>
      <span aria-hidden="true" className="hidden h-8 w-px bg-border sm:block" />
      <div className="min-w-0">
        <div
          role="timer"
          className={`flex items-center gap-1.5 text-sm ${low ? "text-destructive" : "text-muted-foreground"}`}
        >
          <ClockIcon size={14} className="shrink-0" />
          <span className={`font-semibold tabular-nums ${low ? "" : "text-foreground"}`}>
            {mins}:{secs.toString().padStart(2, "0")}
          </span>
          <span> remaining</span>
        </div>
        <ProgressBar
          fraction={elapsed}
          tone={low ? "danger" : "brand"}
          height="h-1"
          className="mt-1.5 w-28 sm:w-36"
        />
      </div>
    </div>
  );
}
