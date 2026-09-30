"use client";

import dynamic from "next/dynamic";

// Loaded client-only: WebGL/Canvas has no server-rendered equivalent, and
// keeping three.js out of the initial bundle protects functional-page load
// performance per the UI/UX design system decision (3D is scoped to
// loading/setup moments only).
const LoadingSceneInner = dynamic(() => import("./LoadingScene.inner"), {
  ssr: false,
});

export function LoadingScene({ className }: { className?: string }) {
  return (
    <div className={className}>
      <LoadingSceneInner />
    </div>
  );
}
