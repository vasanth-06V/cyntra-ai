/**
 * `scrollIntoView` that honours prefers-reduced-motion: an explicit
 * `behavior: "smooth"` is not overridden by the CSS reduced-motion rule.
 */
export function scrollIntoViewSafe(el: Element | null | undefined, options: ScrollIntoViewOptions = {}): void {
  if (!el || typeof el.scrollIntoView !== "function") return;
  const reduced =
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  el.scrollIntoView({ ...options, behavior: reduced ? "auto" : "smooth" });
}
