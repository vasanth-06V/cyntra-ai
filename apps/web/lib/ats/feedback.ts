const BULLET = /^\s*(?:[-*•–]|\d+[.)])\s+/;

/**
 * The feedback arrives as one string from the model. Models write lists in
 * many shapes ("- x", "* x", "1. x", "• x", **bold** lead-ins, an intro
 * line). Turn that into clean plain-text items for rendering.
 */
export function parseFeedback(raw: string): string[] {
  const items: string[] = [];
  for (const line of raw.split(/\r?\n/)) {
    const cleaned = line
      .replace(BULLET, "")
      .replace(/\*\*(.+?)\*\*/g, "$1")
      .replace(/__(.+?)__/g, "$1")
      .replace(/`([^`]+)`/g, "$1")
      .trim();
    if (!cleaned) continue;
    if (!BULLET.test(line) && items.length > 0) {
      // a wrapped continuation of the previous bullet
      items[items.length - 1] += ` ${cleaned}`;
    } else {
      items.push(cleaned);
    }
  }
  // a lone intro line such as "Here are some tips:" is not an action item
  return items.filter((t, i) => !(i === 0 && items.length > 1 && /:$/.test(t)));
}
