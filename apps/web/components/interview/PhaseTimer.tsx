export function PhaseTimer({
  phase,
  minutesRemaining,
}: {
  phase: string;
  minutesRemaining: number;
}) {
  const mins = Math.floor(minutesRemaining);
  const secs = Math.max(0, Math.round((minutesRemaining - mins) * 60));
  const low = minutesRemaining <= 5;

  return (
    <div className="flex items-center gap-3 rounded-lg border border-border px-3 py-1.5 text-sm">
      <span className="font-medium capitalize">{phase.replace(/_/g, " ")}</span>
      <span className={low ? "text-destructive" : "text-muted-foreground"}>
        {mins}:{secs.toString().padStart(2, "0")} remaining
      </span>
    </div>
  );
}
