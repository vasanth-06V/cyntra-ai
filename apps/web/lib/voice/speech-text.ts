/**
 * Prepares an interviewer reply for speech: markdown noise removed, then cut
 * into sentence-sized pieces. Short pieces matter twice: "stop" takes effect
 * at once (only the current piece is cancelled), and some browsers cut off a
 * single utterance that runs longer than about fifteen seconds.
 */

export function toSpeakable(text: string): string {
  return text
    .replace(/```[\s\S]*?```/g, " (code omitted) ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\*\*(.+?)\*\*/g, "$1")
    .replace(/[*_#>]+/g, " ")
    .replace(/https?:\/\/\S+/g, " link ")
    .replace(/\s+/g, " ")
    .trim();
}

export function splitForSpeech(text: string, maxLen = 180): string[] {
  const clean = toSpeakable(text);
  if (!clean) return [];

  const sentences = clean.split(/(?<=[.!?])\s+/);
  const pieces: string[] = [];
  for (const sentence of sentences) {
    if (sentence.length <= maxLen) {
      pieces.push(sentence);
      continue;
    }
    // A very long sentence: break at commas/semicolons, then at spaces.
    let rest = sentence;
    while (rest.length > maxLen) {
      const window = rest.slice(0, maxLen);
      let cut = Math.max(window.lastIndexOf(", "), window.lastIndexOf("; "));
      if (cut < maxLen * 0.4) cut = window.lastIndexOf(" ");
      if (cut <= 0) cut = maxLen;
      pieces.push(rest.slice(0, cut + 1).trim());
      rest = rest.slice(cut + 1).trim();
    }
    if (rest) pieces.push(rest);
  }
  return pieces.filter(Boolean);
}
