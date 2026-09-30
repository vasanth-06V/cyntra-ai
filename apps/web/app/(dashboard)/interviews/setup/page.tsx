import { LoadingScene } from "@/components/three/LoadingScene";

export default function InterviewSetupPage() {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-16 text-center">
      <LoadingScene className="h-64 w-64" />
      <h1 className="text-xl font-semibold">Setting up your interview…</h1>
      <p className="max-w-sm text-sm text-muted-foreground">
        This is a design-system preview of the 3D loading scene. The real
        resume/JD upload flow and progress states are built in a later phase.
      </p>
    </div>
  );
}
