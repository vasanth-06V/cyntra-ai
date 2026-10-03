/** Thin wrapper over the browser's speech recognition (Chrome/Edge/Safari-partial). */

export type RecognizerError =
  | "not-allowed" // microphone permission denied or blocked
  | "no-speech" // the browser heard nothing for a while (normal)
  | "network" // the recognizer's service could not be reached
  | "audio-capture" // no microphone
  | "other";

type RecognitionResultLike = { 0: { transcript: string }; isFinal: boolean; length: number };
type RecognitionEventLike = { results: ArrayLike<RecognitionResultLike> };
type RecognitionErrorLike = { error: string };

interface RecognitionLike {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onstart: (() => void) | null;
  onend: (() => void) | null;
  onresult: ((e: RecognitionEventLike) => void) | null;
  onerror: ((e: RecognitionErrorLike) => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

type RecognitionCtor = new () => RecognitionLike;

export function getRecognitionCtor(): RecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: RecognitionCtor;
    webkitSpeechRecognition?: RecognitionCtor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export function mapRecognitionError(code: string): RecognizerError | null {
  switch (code) {
    case "not-allowed":
    case "service-not-allowed":
      return "not-allowed";
    case "no-speech":
      return "no-speech";
    case "network":
      return "network";
    case "audio-capture":
      return "audio-capture";
    case "aborted":
      return null; // we asked for it
    default:
      return "other";
  }
}

export type RecognizerHandlers = {
  onStart: () => void;
  /** The full transcript of the running session (final + interim). */
  onTranscript: (text: string) => void;
  onEnd: () => void;
  onError: (error: RecognizerError) => void;
};

export type Recognizer = { start: () => void; stop: () => void };

export function createRecognizer(handlers: RecognizerHandlers, lang = "en-US"): Recognizer | null {
  const Ctor = getRecognitionCtor();
  if (!Ctor) return null;

  const rec = new Ctor();
  rec.continuous = true;
  rec.interimResults = true;
  rec.lang = lang;
  rec.onstart = () => handlers.onStart();
  rec.onend = () => handlers.onEnd();
  rec.onerror = (e) => {
    const mapped = mapRecognitionError(e.error);
    if (mapped) handlers.onError(mapped);
  };
  rec.onresult = (e) => {
    let text = "";
    for (let i = 0; i < e.results.length; i++) text += e.results[i][0].transcript + " ";
    handlers.onTranscript(text.trim());
  };

  return {
    start() {
      try {
        rec.start();
      } catch {
        // already started: nothing to do
      }
    },
    stop() {
      try {
        rec.abort();
      } catch {
        // not running
      }
    },
  };
}
