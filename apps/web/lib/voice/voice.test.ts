import { describe, expect, it, vi } from "vitest";
import { parseFeedback } from "../ats/feedback";
import { UtteranceBuffer, type Timers } from "./endpointing";
import { mapRecognitionError } from "./recognizer";
import { DEFAULT_SETTINGS, loadSettings, sanitizeSettings, saveSettings } from "./settings";
import { splitForSpeech, toSpeakable } from "./speech-text";

/** A clock the tests drive by hand. */
function fakeClock() {
  let now = 0;
  let nextId = 1;
  const pending = new Map<number, { at: number; fn: () => void }>();
  const timers: Timers = {
    set: (fn, ms) => {
      const id = nextId++;
      pending.set(id, { at: now + ms, fn });
      return id;
    },
    clear: (id) => void pending.delete(id as number),
  };
  return {
    timers,
    advance(ms: number) {
      now += ms;
      for (const [id, t] of [...pending]) {
        if (t.at <= now) {
          pending.delete(id);
          t.fn();
        }
      }
    },
    get timersPending() {
      return pending.size;
    },
  };
}

describe("UtteranceBuffer (when is an answer finished?)", () => {
  it("fires once, after the silence, with everything heard", () => {
    const clock = fakeClock();
    const ready = vi.fn();
    const buf = new UtteranceBuffer(2500, ready, clock.timers);

    buf.update("I would use");
    clock.advance(1000);
    buf.update("I would use a hash map"); // more speech restarts the wait
    clock.advance(2400);
    expect(ready).not.toHaveBeenCalled();
    clock.advance(200);
    expect(ready).toHaveBeenCalledExactlyOnceWith("I would use a hash map");
  });

  it("keeps the words across the browser's own session restarts", () => {
    const clock = fakeClock();
    const ready = vi.fn();
    const buf = new UtteranceBuffer(2000, ready, clock.timers);

    buf.update("First I check the input");
    buf.endSession(); // the recognizer ended itself during a pause
    expect(buf.text).toBe("First I check the input");
    buf.update("then I build a map"); // a new session starts from empty
    expect(buf.text).toBe("First I check the input then I build a map");
    clock.advance(2100);
    expect(ready).toHaveBeenCalledWith("First I check the input then I build a map");
  });

  it("never fires for silence alone", () => {
    const clock = fakeClock();
    const ready = vi.fn();
    const buf = new UtteranceBuffer(1500, ready, clock.timers);
    buf.update("   ");
    clock.advance(10_000);
    expect(ready).not.toHaveBeenCalled();
    expect(clock.timersPending).toBe(0);
  });

  it("an edited caption replaces the heard words and cancels the pending send", () => {
    const clock = fakeClock();
    const ready = vi.fn();
    const buf = new UtteranceBuffer(1500, ready, clock.timers);
    buf.update("use a hash mop");
    buf.setText("use a hash map");
    clock.advance(5000);
    expect(ready).not.toHaveBeenCalled();
    expect(buf.text).toBe("use a hash map");
  });

  it("reset forgets the answer and its timer", () => {
    const clock = fakeClock();
    const ready = vi.fn();
    const buf = new UtteranceBuffer(1500, ready, clock.timers);
    buf.update("something");
    buf.reset();
    clock.advance(5000);
    expect(ready).not.toHaveBeenCalled();
    expect(buf.text).toBe("");
  });

  it("the silence length can change between answers", () => {
    const clock = fakeClock();
    const ready = vi.fn();
    const buf = new UtteranceBuffer(1500, ready, clock.timers);
    buf.setSilenceMs(4000);
    buf.update("a long thoughtful answer");
    clock.advance(3900);
    expect(ready).not.toHaveBeenCalled();
    clock.advance(200);
    expect(ready).toHaveBeenCalledOnce();
  });
});

describe("speech text", () => {
  it("removes markdown and code before speaking", () => {
    expect(toSpeakable("**Great.** Use `a hash map`.\n```py\nx=1\n```\nSee https://x.dev/a now")).toBe(
      "Great. Use a hash map. (code omitted) See link now"
    );
  });

  it("splits into sentences, keeps short replies whole", () => {
    expect(splitForSpeech("Thanks. How would you scale that? Walk me through it.")).toEqual([
      "Thanks.",
      "How would you scale that?",
      "Walk me through it.",
    ]);
    expect(splitForSpeech("")).toEqual([]);
  });

  it("breaks a very long sentence into pieces under the limit", () => {
    const long = Array.from({ length: 60 }, (_, i) => `word${i}`).join(" ") + ".";
    const pieces = splitForSpeech(long, 100);
    expect(pieces.length).toBeGreaterThan(3);
    expect(pieces.every((p) => p.length <= 100)).toBe(true);
    expect(pieces.join(" ")).toBe(long);
  });
});

describe("settings", () => {
  it("falls back to defaults for anything malformed", () => {
    expect(sanitizeSettings(null)).toEqual(DEFAULT_SETTINGS);
    const s = sanitizeSettings({ silenceMs: "fast", rate: 99, enabled: "yes", voiceName: 5, allowInterrupt: true });
    expect(s.silenceMs).toBe(DEFAULT_SETTINGS.silenceMs);
    expect(s.rate).toBe(1.4); // clamped
    expect(s.enabled).toBe(false);
    expect(s.voiceName).toBeNull();
    expect(s.allowInterrupt).toBe(true);
  });

  it("round-trips through storage and survives a broken storage", () => {
    const data = new Map<string, string>();
    const storage = { getItem: (k: string) => data.get(k) ?? null, setItem: (k: string, v: string) => void data.set(k, v) };
    saveSettings({ ...DEFAULT_SETTINGS, enabled: true, consented: true, silenceMs: 4000 }, storage);
    expect(loadSettings(storage)).toMatchObject({ enabled: true, consented: true, silenceMs: 4000 });

    const broken = { getItem: () => { throw new Error("blocked"); }, setItem: () => { throw new Error("blocked"); } };
    expect(loadSettings(broken)).toEqual(DEFAULT_SETTINGS);
    expect(() => saveSettings(DEFAULT_SETTINGS, broken)).not.toThrow();
    storage.setItem("cyntra:voice", "{not json");
    expect(loadSettings(storage)).toEqual(DEFAULT_SETTINGS);
  });
});

describe("recognizer errors", () => {
  it("maps the browser's codes and ignores our own aborts", () => {
    expect(mapRecognitionError("not-allowed")).toBe("not-allowed");
    expect(mapRecognitionError("service-not-allowed")).toBe("not-allowed");
    expect(mapRecognitionError("no-speech")).toBe("no-speech");
    expect(mapRecognitionError("network")).toBe("network");
    expect(mapRecognitionError("audio-capture")).toBe("audio-capture");
    expect(mapRecognitionError("aborted")).toBeNull();
    expect(mapRecognitionError("weird")).toBe("other");
  });
});

describe("ATS feedback parser", () => {
  it("turns model text into clean tips", () => {
    expect(parseFeedback("Here are tips:\n* **Add Docker** to skills\n  and projects.\n2. Quantify impact\n- Use `Kubernetes` terms")).toEqual([
      "Add Docker to skills and projects.",
      "Quantify impact",
      "Use Kubernetes terms",
    ]);
    expect(parseFeedback("")).toEqual([]);
  });
});
