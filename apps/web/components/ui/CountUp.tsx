"use client";

import { animate, useReducedMotion } from "framer-motion";
import { useEffect, useState } from "react";

/**
 * Counts up to `value` once. Screen readers get the final number only; people
 * who prefer reduced motion see the final number immediately.
 */
export function CountUp({ value, duration = 1 }: { value: number; duration?: number }) {
  const reduced = useReducedMotion();
  const [current, setCurrent] = useState(0);

  useEffect(() => {
    if (reduced) return;
    const controls = animate(0, value, {
      duration,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (latest) => setCurrent(Math.round(latest)),
    });
    return () => controls.stop();
  }, [value, duration, reduced]);

  return (
    <>
      <span aria-hidden="true">{reduced ? value : current}</span>
      <span className="sr-only">{value}</span>
    </>
  );
}
