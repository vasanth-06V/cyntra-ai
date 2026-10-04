// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { DEFAULT_SETTINGS, type VoiceSettings } from "./settings";
import type { RecognizerError, RecognizerHandlers } from "./recognizer";

// The hook is exercised against a fake recognizer and a fake synthesizer, so
// the real state machine (listening, endpointing, nudges) runs without a browser.
const fakes = vi.hoisted(() => {
  const state = {
    handlers: null as RecognizerHandlers | null,
    start: null as unknown as ReturnType<typeof import("vitest").vi.fn>,
    stop: null as unknown as ReturnType<typeof import("vitest").vi.fn>,
    spoken: [] as string[],
    pending: [] as (() => void)[],
    cancel: null as unknown as ReturnType<typeof import("vitest").vi.fn>,
  };
  return state;
});

vi.mock("./recognizer", () => ({
  getRecognitionCtor: () => class {},
  createRecognizer: (handlers: RecognizerHandlers) => {
    fakes.handlers = handlers;
    return { start: fakes.start, stop: fakes.stop };
  },
}));

vi.mock("./synthesizer", () => ({
  synthesisSupported: () => true,
  listVoices: () => [],
  // Like the real one: a new utterance cancels the previous, whose promise then resolves.
  speak: (text: string) => {
    fakes.pending.splice(0).forEach((resolve) => resolve());
    fakes.spoken.push(text);
    return new Promise<void>((resolve) => fakes.pending.push(resolve));
  },
  cancelSpeech: () => {
    fakes.cancel();
    fakes.pending.splice(0).forEach((resolve) => resolve());
  },
}));

import { CONFIRM_MS, NUDGE_AFTER_MS, useVoice } from "./useVoice";

type Props = {
  active: boolean;
  busy: boolean;
  settings: VoiceSettings;
};

const settings: VoiceSettings = { ...DEFAULT_SETTINGS, enabled: true, silenceMs: 1500 };

function setup(initial: Partial<Props> = {}) {
  const onUtterance = vi.fn();
  const lastInterviewerText = vi.fn(() => "Tell me about a hard bug.");
  const hook = renderHook(
    (props: Props) => useVoice({ ...props, onUtterance, lastInterviewerText }),
    { initialProps: { active: true, busy: false, settings, ...initial } }
  );
  return { ...hook, onUtterance, lastInterviewerText };
}

/** Lets the current utterance finish, like the browser's `end` event. */
async function finishSpeaking() {
  await act(async () => {
    fakes.pending.splice(0).forEach((resolve) => resolve());
  });
}

const transcript = (text: string) => act(() => fakes.handlers!.onTranscript(text));
const fail = (error: RecognizerError) => act(() => fakes.handlers!.onError(error));

beforeEach(() => {
  vi.useFakeTimers();
  fakes.handlers = null;
  fakes.spoken = [];
  fakes.pending = [];
  fakes.cancel = vi.fn();
  // The fake microphone reports start/end synchronously, like the events do.
  fakes.start = vi.fn(() => fakes.handlers?.onStart());
  fakes.stop = vi.fn(() => fakes.handlers?.onEnd());
});

afterEach(() => {
  vi.useRealTimers();
});

describe("useVoice listening", () => {
  it("starts the microphone when voice is active and rests it while an answer is being sent", () => {
    const { result, rerender } = setup();
    expect(fakes.start).toHaveBeenCalledTimes(1);
    expect(result.current.listening).toBe(true);

    rerender({ active: true, busy: true, settings });
    expect(fakes.stop).toHaveBeenCalled();
    expect(result.current.listening).toBe(false);

    rerender({ active: true, busy: false, settings });
    expect(fakes.start).toHaveBeenCalledTimes(2);
    expect(result.current.listening).toBe(true);
  });

  it("does not listen while voice is off", () => {
    const { result } = setup({ active: false });
    expect(fakes.start).not.toHaveBeenCalled();
    expect(result.current.listening).toBe(false);
  });

  it("does not listen while the interviewer speaks, and resumes afterwards", async () => {
    const { result } = setup();
    expect(result.current.listening).toBe(true);

    act(() => void result.current.speak("Welcome."));
    expect(result.current.speaking).toBe(true);
    expect(result.current.listening).toBe(false);

    const starts = fakes.start.mock.calls.length;
    await finishSpeaking();
    expect(result.current.speaking).toBe(false);
    expect(fakes.start.mock.calls.length).toBe(starts + 1);
    expect(result.current.listening).toBe(true);
  });
});

describe("useVoice endpointing", () => {
  it("sends the answer exactly once after the silence and the short confirm window", () => {
    const { result, onUtterance } = setup();
    transcript("I would use a hash map");
    expect(result.current.caption).toBe("I would use a hash map");

    act(() => void vi.advanceTimersByTime(1500));
    expect(result.current.pending).toBe(true);
    expect(onUtterance).not.toHaveBeenCalled();

    act(() => void vi.advanceTimersByTime(CONFIRM_MS));
    expect(onUtterance).toHaveBeenCalledTimes(1);
    expect(onUtterance).toHaveBeenCalledWith("I would use a hash map");
    expect(result.current.pending).toBe(false);
    expect(result.current.caption).toBe("");

    act(() => void vi.advanceTimersByTime(10_000));
    expect(onUtterance).toHaveBeenCalledTimes(1);
  });

  it("does not send when the candidate steps in to edit, and sends the edited words on request", () => {
    const { result, onUtterance } = setup();
    transcript("I would use a hash mop");
    act(() => void vi.advanceTimersByTime(1500));
    expect(result.current.pending).toBe(true);

    act(() => result.current.edit());
    expect(result.current.editing).toBe(true);
    expect(result.current.pending).toBe(false);

    act(() => void vi.advanceTimersByTime(CONFIRM_MS * 3));
    expect(onUtterance).not.toHaveBeenCalled();

    act(() => result.current.changeCaption("I would use a hash map"));
    act(() => result.current.sendNow());
    expect(onUtterance).toHaveBeenCalledTimes(1);
    expect(onUtterance).toHaveBeenCalledWith("I would use a hash map");
    expect(result.current.editing).toBe(false);
  });

  it("keeps words across recognition sessions of one answer", () => {
    const { onUtterance } = setup();
    transcript("first part");
    // The browser ends the session on its own, then a new one starts.
    act(() => fakes.handlers!.onEnd());
    act(() => void vi.advanceTimersByTime(300));
    transcript("second part");
    act(() => void vi.advanceTimersByTime(1500 + CONFIRM_MS));
    expect(onUtterance).toHaveBeenCalledWith("first part second part");
  });
});

describe("useVoice nudges", () => {
  it("nudges after silence, then repeats the question, then stops", async () => {
    const { result } = setup();
    act(() => void result.current.speak("Tell me about a hard bug."));
    await finishSpeaking();
    expect(fakes.spoken).toEqual(["Tell me about a hard bug."]);

    await act(async () => void vi.advanceTimersByTime(NUDGE_AFTER_MS));
    expect(fakes.spoken.at(-1)).toBe("Take your time. I'm listening.");
    await finishSpeaking();

    await act(async () => void vi.advanceTimersByTime(NUDGE_AFTER_MS));
    expect(fakes.spoken.at(-1)).toBe("Let me repeat that. Tell me about a hard bug.");
    await finishSpeaking();

    const count = fakes.spoken.length;
    await act(async () => void vi.advanceTimersByTime(NUDGE_AFTER_MS * 3));
    expect(fakes.spoken.length).toBe(count);
  });

  it("does not nudge a candidate who has started talking", async () => {
    const { result } = setup();
    act(() => void result.current.speak("Question?"));
    await finishSpeaking();
    transcript("well, let me think");
    await act(async () => void vi.advanceTimersByTime(NUDGE_AFTER_MS));
    expect(fakes.spoken).toEqual(["Question?"]);
  });
});

describe("useVoice regressions", () => {
  it("M-3: speaks the pending question from the click that turns voice on (forced), once", async () => {
    const { result, rerender } = setup({ active: false, settings: { ...settings, enabled: false } });

    // Without force the stale `active` flag makes the call a no-op.
    await act(async () => void result.current.speak("Open question"));
    expect(fakes.spoken).toEqual([]);

    // The click handler speaks in the same tick as switching voice on.
    fakes.cancel.mockClear(); // (the initial voice-off mount cancels once)
    act(() => void result.current.speak("Open question", { force: true }));
    expect(fakes.spoken).toEqual(["Open question"]);
    expect(result.current.speaking).toBe(true);

    rerender({ active: true, busy: false, settings });
    expect(fakes.spoken).toEqual(["Open question"]); // not spoken twice
    expect(result.current.speaking).toBe(true);
    expect(fakes.cancel).not.toHaveBeenCalled(); // enabling must not cut it off

    await finishSpeaking();
    expect(result.current.speaking).toBe(false);
    expect(result.current.listening).toBe(true);
  });

  it("M-5: a superseded utterance finishing late does not reopen the microphone", async () => {
    const { result } = setup();
    act(() => void result.current.speak("Take your time."));
    act(() => void result.current.speak("Here is my reply."));
    // The first promise resolves (it was cancelled by the second) while the reply plays.
    await act(async () => {});
    expect(result.current.speaking).toBe(true);
    expect(result.current.listening).toBe(false);
    const starts = fakes.start.mock.calls.length;
    act(() => void vi.advanceTimersByTime(1000));
    expect(fakes.start.mock.calls.length).toBe(starts);

    await finishSpeaking();
    expect(result.current.speaking).toBe(false);
    expect(result.current.listening).toBe(true);
  });

  it("M-6: a blocked microphone can be retried without reloading", () => {
    const { result, rerender } = setup();
    fail("not-allowed");
    expect(result.current.error).toBe("not-allowed");
    expect(result.current.listening).toBe(false);

    const starts = fakes.start.mock.calls.length;
    act(() => result.current.clearError());
    expect(result.current.error).toBeNull();
    expect(fakes.start.mock.calls.length).toBe(starts + 1);
    expect(result.current.listening).toBe(true);

    // Turning voice off and on again also starts from a clean slate.
    fail("audio-capture");
    expect(result.current.error).toBe("audio-capture");
    rerender({ active: false, busy: false, settings: { ...settings, enabled: false } });
    act(() => void vi.advanceTimersByTime(10));
    expect(result.current.error).toBeNull();
    rerender({ active: true, busy: false, settings });
    expect(result.current.listening).toBe(true);
  });

  it("ignores the normal no-speech timeout instead of reporting an error", () => {
    const { result } = setup();
    fail("no-speech");
    expect(result.current.error).toBeNull();
  });

  it("stops talking and listening when voice is switched off", async () => {
    const { result, rerender } = setup();
    act(() => void result.current.speak("Question"));
    expect(result.current.speaking).toBe(true);
    rerender({ active: false, busy: false, settings: { ...settings, enabled: false } });
    await act(async () => void vi.advanceTimersByTime(10));
    expect(fakes.cancel).toHaveBeenCalled();
    expect(result.current.speaking).toBe(false);
    expect(result.current.listening).toBe(false);
  });
});

describe("useVoice cleanup", () => {
  it("stops the microphone, speech and timers on unmount", async () => {
    const { result, unmount, onUtterance } = setup();
    transcript("half an answer");
    act(() => void vi.advanceTimersByTime(1500)); // "Sending..." countdown running
    act(() => void result.current.speak("x"));
    fakes.stop.mockClear();
    fakes.cancel.mockClear();

    unmount();
    expect(fakes.stop).toHaveBeenCalled();
    expect(fakes.cancel).toHaveBeenCalled();
    act(() => void vi.advanceTimersByTime(60_000));
    expect(onUtterance).not.toHaveBeenCalled();
  });
});
