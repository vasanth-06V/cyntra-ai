"use client";

import { useTheme } from "next-themes";
import { useSyncExternalStore } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { flushSync } from "react-dom";

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

function SunIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-[18px] w-[18px]">
      <circle cx="12" cy="12" r="4" stroke="currentColor" strokeWidth="2" />
      <path
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        d="M12 2v2.5M12 19.5V22M4.22 4.22l1.77 1.77M18 18l1.78 1.78M2 12h2.5M19.5 12H22M4.22 19.78 6 18M18 6l1.78-1.78"
      />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-[18px] w-[18px]">
      <path
        fill="currentColor"
        d="M20.5 14.5a8.5 8.5 0 1 1-9-13 7 7 0 0 0 9 13Z"
      />
    </svg>
  );
}

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const mounted = useMounted();

  if (!mounted) {
    return <div className="h-9 w-9 rounded-full border border-transparent" />;
  }

  const isDark = resolvedTheme === "dark";

  // Cross-fade the whole page where the View Transitions API exists; elsewhere
  // (and for people who prefer reduced motion) the theme simply switches.
  function toggle() {
    const next = isDark ? "light" : "dark";
    const start = (document as Document & { startViewTransition?: (cb: () => void) => unknown })
      .startViewTransition;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!start || reduce) {
      setTheme(next);
      return;
    }
    let applied = false;
    const apply = () => {
      if (applied) return;
      applied = true;
      flushSync(() => setTheme(next));
    };
    start.call(document, apply);
    // Safety net: if the browser never gets to render (e.g. a throttled
    // frame), the theme must still change.
    setTimeout(apply, 300);
  }

  return (
    <button
      type="button"
      aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}
      onClick={toggle}
      className="flex h-9 w-9 items-center justify-center overflow-hidden rounded-full border border-border bg-card text-foreground shadow-xs transition-colors duration-150 hover:border-border-strong hover:bg-accent hover:text-accent-foreground cursor-pointer"
    >
      <AnimatePresence mode="wait" initial={false}>
        <motion.span
          key={isDark ? "moon" : "sun"}
          initial={{ rotate: -90, opacity: 0 }}
          animate={{ rotate: 0, opacity: 1 }}
          exit={{ rotate: 90, opacity: 0 }}
          transition={{ duration: 0.2, ease: "easeInOut" }}
          className="flex items-center justify-center"
        >
          {isDark ? <MoonIcon /> : <SunIcon />}
        </motion.span>
      </AnimatePresence>
    </button>
  );
}
