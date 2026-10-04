// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import { cancelSpeech, listVoices, pickVoice, speak, synthesisSupported } from "./synthesizer";

// A fake speechSynthesis: utterances queue up and the test ends them like the browser would.
class FakeUtterance {
  voice: unknown = null;
  rate = 1;
  onend: (() => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(public text: string) {}
}

const voices = [
  { name: "Plain", lang: "en-US" },
  { name: "Google UK English", lang: "en-GB" },
  { name: "Microsoft Aria Online (Natural)", lang: "en-US" },
  { name: "Deutsch", lang: "de-DE" },
];

let spoken: FakeUtterance[];
const synth = {
  speak: vi.fn((u: FakeUtterance) => void spoken.push(u)),
  cancel: vi.fn(() => {
    // the browser fires an error/end event for the interrupted utterance
    const interrupted = spoken.splice(0);
    interrupted.forEach((u) => u.onerror?.());
  }),
  getVoices: () => voices,
};

beforeEach(() => {
  spoken = [];
  synth.speak.mockClear();
  synth.cancel.mockClear();
  (window as unknown as { speechSynthesis: unknown }).speechSynthesis = synth;
  (globalThis as unknown as { SpeechSynthesisUtterance: unknown }).SpeechSynthesisUtterance = FakeUtterance;
  cancelSpeech(); // invalidate any utterance left from a previous test
  synth.speak.mockClear();
  synth.cancel.mockClear();
});

describe("voices", () => {
  it("lists English voices only", () => {
    expect(listVoices().map((v) => v.name)).toEqual(["Plain", "Google UK English", "Microsoft Aria Online (Natural)"]);
  });

  it("prefers a natural/online voice, honours the user's choice, and falls back when it is gone", () => {
    expect(pickVoice(null)?.name).toBe("Microsoft Aria Online (Natural)");
    expect(pickVoice("Plain")?.name).toBe("Plain");
    expect(pickVoice("Removed voice")?.name).toBe("Microsoft Aria Online (Natural)");
  });

  it("reports support from the presence of speechSynthesis", () => {
    expect(synthesisSupported()).toBe(true);
    delete (window as unknown as { speechSynthesis?: unknown }).speechSynthesis;
    expect(synthesisSupported()).toBe(false);
  });
});

describe("speak", () => {
  it("speaks sentence by sentence and resolves after the last one ends", async () => {
    let done = false;
    const p = speak("First sentence. Second sentence.", { voiceName: null, rate: 1.2 }).then(() => (done = true));
    expect(spoken).toHaveLength(1);
    expect(spoken[0].text).toBe("First sentence.");
    expect(spoken[0].rate).toBe(1.2);
    spoken.shift()!.onend!();
    expect(spoken[0].text).toBe("Second sentence.");
    await Promise.resolve();
    expect(done).toBe(false);
    spoken.shift()!.onend!();
    await p;
    expect(done).toBe(true);
  });

  it("resolves at once for empty text or when speech is unsupported", async () => {
    await expect(speak("   ", { voiceName: null, rate: 1 })).resolves.toBeUndefined();
    expect(synth.speak).not.toHaveBeenCalled();
    delete (window as unknown as { speechSynthesis?: unknown }).speechSynthesis;
    await expect(speak("Hello.", { voiceName: null, rate: 1 })).resolves.toBeUndefined();
  });

  it("a new speak cancels the previous one, which then stops after its current piece", async () => {
    const first = speak("One. Two. Three.", { voiceName: null, rate: 1 });
    const second = speak("Fresh.", { voiceName: null, rate: 1 });
    await first; // resolved by the cancel
    expect(spoken.map((u) => u.text)).toEqual(["Fresh."]);
    spoken.shift()!.onend!();
    await second;
    // the superseded speech never queued its remaining sentences
    expect(synth.speak.mock.calls.map((c) => (c[0] as FakeUtterance).text)).toEqual(["One.", "Fresh."]);
  });

  it("cancelSpeech silences the current speech and resolves its promise", async () => {
    const p = speak("Long answer. More text.", { voiceName: null, rate: 1 });
    cancelSpeech();
    await p;
    expect(synth.cancel).toHaveBeenCalled();
    expect(spoken).toHaveLength(0);
  });

  it("resolves (does not hang) when the browser reports an error", async () => {
    const p = speak("Hello there.", { voiceName: null, rate: 1 });
    spoken[0].onerror!();
    await expect(p).resolves.toBeUndefined();
  });
});
