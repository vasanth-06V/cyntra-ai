"use client";

import { useTheme } from "next-themes";
import { useSyncExternalStore } from "react";
import { motion } from "framer-motion";

const noopSubscribe = () => () => {};

/**
 * Avoids a hydration mismatch: the server doesn't know the viewer's
 * preferred/stored theme, so the toggle renders nothing until mounted.
 * useSyncExternalStore (rather than setState-in-an-effect) is the
 * React-recommended way to read this kind of client-only fact.
 */
function useMounted() {
  return useSyncExternalStore(
    noopSubscribe,
    () => true,
    () => false
  );
}

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const mounted = useMounted();

  if (!mounted) {
    return <div className="h-9 w-16 rounded-full" />;
  }

  const isDark = resolvedTheme === "dark";

  return (
    <button
      type="button"
      role="switch"
      aria-checked={isDark}
      aria-label="Toggle theme"
      onClick={() => setTheme(isDark ? "light" : "dark")}
      className="relative h-9 w-16 rounded-full border border-border bg-secondary p-1 transition-colors cursor-pointer"
    >
      <motion.span
        layout
        transition={{ type: "spring", stiffness: 500, damping: 30 }}
        className="flex h-7 w-7 items-center justify-center rounded-full bg-primary text-primary-foreground text-sm"
        style={{ marginLeft: isDark ? "1.75rem" : "0rem" }}
      >
        {isDark ? "🌙" : "☀️"}
      </motion.span>
    </button>
  );
}
