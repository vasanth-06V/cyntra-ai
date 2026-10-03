"use client";

import dynamic from "next/dynamic";
import { useSyncExternalStore } from "react";

// Loaded client-only: WebGL/Canvas has no server-rendered equivalent, and
// keeping three.js out of the initial bundle protects functional-page load
// performance per the UI/UX design system decision (3D is scoped to
// loading/setup moments only).
const LoadingSceneInner = dynamic(() => import("./LoadingScene.inner"), {
  ssr: false,
});

const QUERY = "(prefers-reduced-motion: reduce)";
const subscribe = (notify: () => void) => {
  const media = window.matchMedia(QUERY);
  media.addEventListener("change", notify);
  return () => media.removeEventListener("change", notify);
};
const prefersReducedMotion = () => window.matchMedia(QUERY).matches;

export function LoadingScene({ className }: { className?: string }) {
  const reduced = useSyncExternalStore(subscribe, prefersReducedMotion, () => false);
  // A spinning 3D shape is decoration; people who ask for less motion get a still frame.
  if (reduced) return <div className={className} aria-hidden="true" />;
  return (
    <div className={className} aria-hidden="true">
      <LoadingSceneInner />
    </div>
  );
}
