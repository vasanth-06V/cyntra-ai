/** Thin wrapper over the browser's speech synthesis. */

import { splitForSpeech } from "./speech-text";

export function synthesisSupported(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

export function listVoices(): SpeechSynthesisVoice[] {
  return synthesisSupported()
    ? window.speechSynthesis.getVoices().filter((v) => v.lang.toLowerCase().startsWith("en"))
    : [];
}

/** The most natural-sounding English voice available, unless the user picked one. */
export function pickVoice(preferred: string | null): SpeechSynthesisVoice | null {
  const voices = listVoices();
  if (preferred) {
    const chosen = voices.find((v) => v.name === preferred);
    if (chosen) return chosen;
  }
  const rank = (v: SpeechSynthesisVoice) =>
    (/natural|neural|online/i.test(v.name) ? 3 : 0) +
    (/google/i.test(v.name) ? 2 : 0) +
    (v.lang.toLowerCase() === "en-us" || v.lang.toLowerCase() === "en-gb" ? 1 : 0);
  return [...voices].sort((a, b) => rank(b) - rank(a))[0] ?? null;
}

export type SpeakOptions = { voiceName: string | null; rate: number };

let generation = 0;

/** Speaks `text` piece by piece. Resolves when finished or cancelled. */
export function speak(text: string, options: SpeakOptions): Promise<void> {
  if (!synthesisSupported()) return Promise.resolve();
  const pieces = splitForSpeech(text);
  if (pieces.length === 0) return Promise.resolve();

  cancelSpeech();
  const mine = ++generation;
  const voice = pickVoice(options.voiceName);

  return new Promise<void>((resolve) => {
    let index = 0;
    const next = () => {
      if (mine !== generation || index >= pieces.length) {
        resolve();
        return;
      }
      const utterance = new SpeechSynthesisUtterance(pieces[index++]);
      if (voice) utterance.voice = voice;
      utterance.rate = options.rate;
      utterance.onend = next;
      utterance.onerror = () => resolve();
      window.speechSynthesis.speak(utterance);
    };
    next();
  });
}

export function cancelSpeech(): void {
  generation++;
  if (synthesisSupported()) window.speechSynthesis.cancel();
}
