"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { SILENCE_CHOICES_MS, type VoiceSettings } from "@/lib/voice/settings";
import { listVoices } from "@/lib/voice/synthesizer";
import { ERROR_TEXT, type useVoice } from "@/lib/voice/useVoice";

type Voice = ReturnType<typeof useVoice>;

type Props = {
  voice: Voice;
  settings: VoiceSettings;
  onSettingsChange: (next: VoiceSettings) => void;
  /** Called from the click that turns voice on (a user gesture is required to speak). */
  onEnable: () => void;
  onDisable: () => void;
  onSendCaption: () => void;
  reviewing: boolean;
  sending: boolean;
};

export function VoiceBar({
  voice,
  settings,
  onSettingsChange,
  onEnable,
  onDisable,
  onSendCaption,
  reviewing,
  sending,
}: Props) {
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);

  // Voices load asynchronously in most browsers.
  useEffect(() => {
    if (!voice.supported) return;
    const load = () => setVoices(listVoices());
    const t = setTimeout(load, 0);
    window.speechSynthesis.addEventListener("voiceschanged", load);
    return () => {
      clearTimeout(t);
      window.speechSynthesis.removeEventListener("voiceschanged", load);
    };
  }, [voice.supported]);

  if (!voice.supported) {
    return (
      <p className="border-t border-border px-4 py-2 text-xs text-muted-foreground">
        Voice isn&apos;t available in this browser (try Chrome or Edge). You can type your answers.
      </p>
    );
  }

  if (!settings.enabled) {
    return (
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border px-4 py-2">
        <p className="text-xs text-muted-foreground">
          {settings.consented
            ? "Answer out loud and hear the interviewer."
            : "Voice uses your browser's speech recognition — in Chrome and Edge your speech is processed by Google. Typing always works."}
        </p>
        <Button type="button" variant="outline" onClick={onEnable}>
          Turn on voice
        </Button>
      </div>
    );
  }

  const status = voice.error
    ? ERROR_TEXT[voice.error]
    : sending
      ? "Sending your answer…"
      : reviewing
        ? "Reviewing your solution…"
        : voice.speaking
          ? "Interviewer is speaking…"
          : voice.pending
            ? "Sending…"
            : voice.editing
              ? "Edit your answer, then send."
              : voice.listening
                ? "Listening — answer out loud."
                : "Microphone resting.";

  return (
    <div className="flex flex-col gap-2 border-t border-border px-4 py-2" aria-live="polite">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p
          role="status"
          className={`text-sm ${voice.error ? "text-destructive" : "text-muted-foreground"}`}
        >
          <span
            aria-hidden="true"
            className={`mr-2 inline-block h-2 w-2 rounded-full ${
              voice.listening ? "animate-pulse bg-green-500" : voice.speaking ? "bg-primary" : "bg-muted-foreground/40"
            }`}
          />
          {status}
        </p>
        <div className="flex items-center gap-2">
          {voice.speaking && (
            <Button type="button" variant="outline" onClick={voice.stopSpeaking}>
              Stop speaking
            </Button>
          )}
          <Button type="button" variant="outline" onClick={onDisable}>
            Turn off voice
          </Button>
        </div>
      </div>

      {(voice.caption || voice.editing) && (
        <div className="flex flex-col gap-2">
          {voice.editing ? (
            <textarea
              value={voice.caption}
              onChange={(e) => voice.changeCaption(e.target.value)}
              aria-label="Your answer"
              rows={3}
              maxLength={4000}
              className="rounded-lg border border-border bg-transparent px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
            />
          ) : (
            <p className="rounded-lg border border-dashed border-border px-3 py-2 text-sm">
              {voice.caption}
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            {voice.pending && (
              <Button type="button" variant="outline" onClick={voice.edit}>
                Edit
              </Button>
            )}
            {voice.editing && (
              <Button type="button" variant="outline" onClick={voice.resume}>
                Keep listening
              </Button>
            )}
            <Button type="button" onClick={onSendCaption} disabled={sending || reviewing || !voice.caption.trim()}>
              Send now
            </Button>
          </div>
        </div>
      )}

      <details className="text-xs text-muted-foreground">
        <summary className="cursor-pointer">Voice settings</summary>
        <div className="mt-2 grid gap-3 sm:grid-cols-2">
          <label className="flex items-center justify-between gap-2">
            Send after silence of
            <select
              value={settings.silenceMs}
              onChange={(e) => onSettingsChange({ ...settings, silenceMs: Number(e.target.value) })}
              className="rounded-lg border border-border bg-transparent px-2 py-1 text-sm"
            >
              {SILENCE_CHOICES_MS.map((ms) => (
                <option key={ms} value={ms}>
                  {ms / 1000}s
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center justify-between gap-2">
            Speed
            <input
              type="range"
              min={0.8}
              max={1.3}
              step={0.1}
              value={settings.rate}
              onChange={(e) => onSettingsChange({ ...settings, rate: Number(e.target.value) })}
              aria-label="Speaking speed"
            />
          </label>
          <label className="flex items-center justify-between gap-2">
            Interviewer voice
            <select
              value={settings.voiceName ?? ""}
              onChange={(e) => onSettingsChange({ ...settings, voiceName: e.target.value || null })}
              className="max-w-[12rem] rounded-lg border border-border bg-transparent px-2 py-1 text-sm"
            >
              <option value="">Automatic</option>
              {voices.map((v) => (
                <option key={v.name} value={v.name}>
                  {v.name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={settings.allowInterrupt}
              onChange={(e) => onSettingsChange({ ...settings, allowInterrupt: e.target.checked })}
            />
            Let me interrupt the interviewer (use headphones)
          </label>
        </div>
      </details>
    </div>
  );
}
