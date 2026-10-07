"use client";

import { useEffect, useState } from "react";
import { formatDateTime } from "@/lib/format";

/**
 * A date in the viewer's own locale and time zone. The server can't know
 * either, so it renders nothing and the browser fills it in after mount
 * (rendering it on the server would not match and trigger a hydration error).
 */
export function LocalTime({ iso, dateOnly = false }: { iso: string; dateOnly?: boolean }) {
  const [text, setText] = useState("");
  useEffect(() => {
    const t = setTimeout(
      () => setText(dateOnly ? (Number.isNaN(new Date(iso).getTime()) ? "" : new Date(iso).toLocaleDateString()) : formatDateTime(iso)),
      0
    );
    return () => clearTimeout(t);
  }, [iso, dateOnly]);
  return <time dateTime={iso}>{text}</time>;
}
