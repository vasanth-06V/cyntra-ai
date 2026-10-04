// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DEFAULT_SETTINGS, type VoiceSettings } from "@/lib/voice/settings";
import { ERROR_TEXT } from "@/lib/voice/useVoice";
import { VoiceBar } from "./VoiceBar";

// VoiceBar only reads these two module-level helpers; no real speech APIs are needed.
vi.mock("@/lib/voice/synthesizer", () => ({ listVoices: () => [] }));

type VoiceProp = Parameters<typeof VoiceBar>[0]["voice"];

function makeVoice(over: Partial<VoiceProp> = {}): VoiceProp {
  return {
    supported: true,
    listening: false,
    speaking: false,
    caption: "",
    pending: false,
    editing: false,
    error: null,
    speak: vi.fn(),
    stopSpeaking: vi.fn(),
    edit: vi.fn(),
    changeCaption: vi.fn(),
    sendNow: vi.fn(),
    resume: vi.fn(),
    clearError: vi.fn(),
    ...over,
  } as VoiceProp;
}

const on: VoiceSettings = { ...DEFAULT_SETTINGS, enabled: true, consented: true };

function setup(voice: VoiceProp, settings: VoiceSettings = on, props: Partial<Parameters<typeof VoiceBar>[0]> = {}) {
  const handlers = { onSettingsChange: vi.fn(), onEnable: vi.fn(), onDisable: vi.fn(), onSendCaption: vi.fn() };
  render(<VoiceBar voice={voice} settings={settings} reviewing={false} sending={false} {...handlers} {...props} />);
  return handlers;
}

beforeEach(() => {
  // listVoices is mocked, but the bar still subscribes to speechSynthesis events
  (window as unknown as { speechSynthesis: unknown }).speechSynthesis = {
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  };
});

describe("VoiceBar", () => {
  it("explains that voice is unavailable and keeps typing possible", () => {
    setup(makeVoice({ supported: false }));
    expect(screen.getByText(/Voice isn't available in this browser/)).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("shows the consent note before the first use and enables voice from the button", async () => {
    const h = setup(makeVoice(), { ...DEFAULT_SETTINGS });
    expect(screen.getByText(/processed by Google/)).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: "Turn on voice" }));
    expect(h.onEnable).toHaveBeenCalledTimes(1);
  });

  it("uses the short hint once the user has already consented", () => {
    setup(makeVoice(), { ...DEFAULT_SETTINGS, consented: true });
    expect(screen.getByText("Answer out loud and hear the interviewer.")).toBeInTheDocument();
  });

  it.each([
    [{ listening: true }, {}, "Listening — answer out loud."],
    [{ speaking: true }, {}, "Interviewer is speaking…"],
    [{ pending: true, caption: "hi" }, {}, "Sending…"],
    [{ editing: true, caption: "hi" }, {}, "Edit your answer, then send."],
    [{}, { sending: true }, "Sending your answer…"],
    [{}, { reviewing: true }, "Reviewing your solution…"],
    [{}, {}, "Microphone resting."],
  ] as const)("reports the state %j %j as %s", (voice, props, text) => {
    setup(makeVoice(voice as Partial<VoiceProp>), on, props as Partial<Parameters<typeof VoiceBar>[0]>);
    expect(screen.getByRole("status")).toHaveTextContent(text);
  });

  it("M-6: shows the microphone error with a 'Try microphone again' action wired to clearError", async () => {
    const voice = makeVoice({ error: "not-allowed" });
    setup(voice);
    expect(screen.getByRole("status")).toHaveTextContent(ERROR_TEXT["not-allowed"]);
    await userEvent.setup().click(screen.getByRole("button", { name: "Try microphone again" }));
    expect(voice.clearError).toHaveBeenCalledTimes(1);
  });

  it("does not offer the retry when there is no error", () => {
    setup(makeVoice());
    expect(screen.queryByRole("button", { name: "Try microphone again" })).not.toBeInTheDocument();
  });

  it("offers 'Stop speaking' only while the interviewer talks", async () => {
    const voice = makeVoice({ speaking: true });
    setup(voice);
    await userEvent.setup().click(screen.getByRole("button", { name: "Stop speaking" }));
    expect(voice.stopSpeaking).toHaveBeenCalledTimes(1);
  });

  it("turns voice off", async () => {
    const h = setup(makeVoice());
    await userEvent.setup().click(screen.getByRole("button", { name: "Turn off voice" }));
    expect(h.onDisable).toHaveBeenCalledTimes(1);
  });

  it("shows the caption during 'Sending…' with Edit, and Send now", async () => {
    const voice = makeVoice({ pending: true, caption: "I would use a map" });
    const h = setup(voice);
    expect(screen.getByText("I would use a map")).toBeInTheDocument();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Edit" }));
    expect(voice.edit).toHaveBeenCalledTimes(1);
    await user.click(screen.getByRole("button", { name: "Send now" }));
    expect(h.onSendCaption).toHaveBeenCalledTimes(1);
  });

  it("lets the candidate edit the caption and keep listening", async () => {
    const voice = makeVoice({ editing: true, caption: "hash mop" });
    setup(voice);
    const box = screen.getByLabelText("Your answer");
    await userEvent.setup().type(box, "!");
    expect(voice.changeCaption).toHaveBeenCalledWith("hash mop!");
    await userEvent.setup().click(screen.getByRole("button", { name: "Keep listening" }));
    expect(voice.resume).toHaveBeenCalledTimes(1);
  });

  it("disables 'Send now' while an answer is being sent or the caption is blank", () => {
    setup(makeVoice({ pending: true, caption: "   " }));
    expect(screen.getByRole("button", { name: "Send now" })).toBeDisabled();
  });
});
