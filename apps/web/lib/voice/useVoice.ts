"use client";

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { UtteranceBuffer } from "./endpointing";
import { createRecognizer, getRecognitionCtor, type Recognizer, type RecognizerError } from "./recognizer";
import type { VoiceSettings } from "./settings";
import { cancelSpeech, speak as speakText, synthesisSupported } from "./synthesizer";

/** How long the "Sending..." moment lasts, so a misheard answer can be edited. */
export const CONFIRM_MS = 1500;
/** Silence after the interviewer finishes before a gentle (canned, free) nudge. */
export const NUDGE_AFTER_MS = 20_000;
const RESTART_DELAY_MS = 250;
const MAX_QUICK_RESTARTS = 5;

const noopSubscribe = () => () => {};
const detect = () => getRecognitionCtor() !== null && synthesisSupported();

export const ERROR_TEXT: Record<RecognizerError, string> = {
  "not-allowed": "Microphone access is blocked. Allow it in your browser's address bar, or type your answers.",
  "audio-capture": "No microphone was found. You can type your answers instead.",
  network: "The browser's speech service could not be reached. You can type your answers meanwhile.",
  "no-speech": "",
  other: "Voice input hit a problem. You can type your answers meanwhile.",
};

type Options = {
  /** Voice mode is on and the interview is running. */
  active: boolean;
  /** The answer is being sent / a solution is being reviewed: the mic rests. */
  busy: boolean;
  settings: VoiceSettings;
  /** A finished answer, ready to send. */
  onUtterance: (text: string) => void;
  /** The interviewer's last message, for "let me repeat that". */
  lastInterviewerText: () => string | null;
};

export function useVoice({ active, busy, settings, onUtterance, lastInterviewerText }: Options) {
  const supported = useSyncExternalStore(noopSubscribe, detect, () => false);

  const [listening, setListening] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [caption, setCaption] = useState("");
  const [pending, setPending] = useState(false); // "Sending..." countdown running
  const [editing, setEditing] = useState(false); // the candidate took over the caption
  const [error, setError] = useState<RecognizerError | null>(null);

  // Latest values for callbacks that outlive a render.
  const live = useRef({ active, busy, settings, onUtterance, lastInterviewerText });
  useEffect(() => {
    live.current = { active, busy, settings, onUtterance, lastInterviewerText };
  });

  const recognizer = useRef<Recognizer | null>(null);
  const buffer = useRef<UtteranceBuffer | null>(null);
  const runningRef = useRef(false);
  const wantRef = useRef(false);
  const speakingRef = useRef(false);
  const confirmTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const nudgeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const nudges = useRef(0);
  const quickRestarts = useRef(0);
  const lastStart = useRef(0);

  const shouldListen =
    supported && active && !busy && !pending && !editing && error !== "not-allowed" && error !== "audio-capture" &&
    (!speaking || settings.allowInterrupt);
  useEffect(() => {
    wantRef.current = shouldListen;
  }, [shouldListen]);

  const clearNudge = useCallback(() => {
    if (nudgeTimer.current) clearTimeout(nudgeTimer.current);
    nudgeTimer.current = null;
  }, []);

  const spoke = useRef(false);

  // Every speak() takes a number; only the newest one may flip `speaking` back
  // to false, so a superseded utterance finishing late cannot reopen the mic.
  const speakGen = useRef(0);

  const speakInternal = useCallback(
    async (text: string, opts: { isNudge?: boolean; force?: boolean } = {}) => {
      // `force`: called from the click that turns voice on, before `live.current.active` has caught up.
      if ((!live.current.active && !opts.force) || !text.trim()) return;
      clearNudge();
      if (!opts.isNudge) nudges.current = 0;
      spoke.current = true;
      speakingRef.current = true;
      setSpeaking(true);
      const mine = ++speakGen.current;
      const { voiceName, rate } = live.current.settings;
      await speakText(text, { voiceName, rate });
      if (mine !== speakGen.current) return;
      speakingRef.current = false;
      setSpeaking(false);
    },
    [clearNudge]
  );

  // After the interviewer finishes talking, wait for the candidate; if the
  // silence drags on, a canned (free, no LLM call) nudge, then a repeat.
  const armNudge = useCallback(() => {
    clearNudge();
    if (!live.current.active || nudges.current >= 2) return;
    nudgeTimer.current = setTimeout(() => {
      if (!live.current.active || live.current.busy || speakingRef.current) return;
      if (buffer.current?.text) return; // they are talking
      const attempt = nudges.current++;
      const last = live.current.lastInterviewerText();
      void speakInternal(
        attempt === 0 || !last ? "Take your time. I'm listening." : `Let me repeat that. ${last}`,
        { isNudge: true }
      );
    }, NUDGE_AFTER_MS);
  }, [clearNudge, speakInternal]);

  useEffect(() => {
    if (!speaking && spoke.current && active) armNudge();
  }, [speaking, active, armNudge]);

  const commit = useCallback((text: string) => {
    if (confirmTimer.current) clearTimeout(confirmTimer.current);
    confirmTimer.current = null;
    buffer.current?.reset();
    setCaption("");
    setPending(false);
    setEditing(false);
    const answer = text.trim();
    if (answer) live.current.onUtterance(answer);
  }, []);

  // The utterance buffer and the recognizer live for the component's lifetime.
  useEffect(() => {
    if (!supported) return;

    const buf = new UtteranceBuffer(live.current.settings.silenceMs, (text) => {
      // Silence long enough: show "Sending..." and send unless the candidate steps in.
      setPending(true);
      recognizer.current?.stop();
      confirmTimer.current = setTimeout(() => commit(text), CONFIRM_MS);
    });
    buffer.current = buf;

    const rec = createRecognizer({
      onStart: () => {
        runningRef.current = true;
        lastStart.current = Date.now();
        setListening(true);
        setError(null);
      },
      onTranscript: (text) => {
        clearNudge();
        if (speakingRef.current && live.current.settings.allowInterrupt) cancelSpeech();
        setCaption(buf.update(text));
      },
      onEnd: () => {
        runningRef.current = false;
        setListening(false);
        buf.endSession();
        if (!wantRef.current) return;
        // Browsers end sessions on their own; start again unless it keeps failing fast.
        quickRestarts.current = Date.now() - lastStart.current < 1000 ? quickRestarts.current + 1 : 0;
        if (quickRestarts.current > MAX_QUICK_RESTARTS) return;
        setTimeout(() => {
          if (wantRef.current && !runningRef.current) recognizer.current?.start();
        }, RESTART_DELAY_MS);
      },
      onError: (e) => {
        if (e !== "no-speech") setError(e);
      },
    });
    recognizer.current = rec;

    return () => {
      buf.dispose();
      rec?.stop();
      cancelSpeech();
      if (confirmTimer.current) clearTimeout(confirmTimer.current);
      clearNudge();
      recognizer.current = null;
      buffer.current = null;
    };
  }, [supported, commit, clearNudge]);

  useEffect(() => {
    buffer.current?.setSilenceMs(settings.silenceMs);
  }, [settings.silenceMs]);

  // Start or rest the microphone as the situation changes.
  useEffect(() => {
    if (!recognizer.current) return;
    if (shouldListen && !runningRef.current) {
      quickRestarts.current = 0;
      recognizer.current.start();
    } else if (!shouldListen && runningRef.current) {
      recognizer.current.stop();
    }
  }, [shouldListen]);

  // Leaving voice mode: stop talking and listening, drop any half answer.
  useEffect(() => {
    if (active) return;
    cancelSpeech();
    clearNudge();
    if (confirmTimer.current) clearTimeout(confirmTimer.current);
    confirmTimer.current = null;
    buffer.current?.reset();
    speakGen.current++;
    speakingRef.current = false;
    const t = setTimeout(() => {
      setCaption("");
      setPending(false);
      setEditing(false);
      setSpeaking(false);
      // A blocked-microphone error must not outlive voice mode: turning voice on again retries.
      setError(null);
    }, 0);
    return () => clearTimeout(t);
  }, [active, clearNudge]);

  /**
   * Speaks `text`; resolves when it has finished (or was cut off). `force` lets a
   * click handler speak in the same tick that switches voice on.
   */
  const speak = useCallback(
    (text: string, opts: { force?: boolean } = {}) => speakInternal(text, { force: opts.force }),
    [speakInternal]
  );
  const clearError = useCallback(() => setError(null), []);

  const stopSpeaking = useCallback(() => {
    cancelSpeech();
  }, []);

  /** Step in during "Sending...": the caption becomes editable. */
  const edit = useCallback(() => {
    if (confirmTimer.current) clearTimeout(confirmTimer.current);
    confirmTimer.current = null;
    setPending(false);
    setEditing(true);
  }, []);

  const changeCaption = useCallback((text: string) => {
    buffer.current?.setText(text);
    setCaption(text);
  }, []);

  const sendNow = useCallback(() => commit(buffer.current?.text || caption), [commit, caption]);

  /** After editing: go back to listening, keeping the (edited) words. */
  const resume = useCallback(() => setEditing(false), []);

  return {
    supported,
    listening,
    speaking,
    caption,
    pending,
    editing,
    error,
    speak,
    stopSpeaking,
    edit,
    changeCaption,
    sendNow,
    resume,
    clearError,
  };
}
