export type VoiceSettings = {
  /** Voice mode on (remembered; the candidate switches it on once). */
  enabled: boolean;
  /** Has seen the one-line note about browser speech recognition. */
  consented: boolean;
  /** Silence after speech before the answer is sent, in ms. */
  silenceMs: number;
  /** Keep listening while the interviewer speaks (needs headphones). */
  allowInterrupt: boolean;
  voiceName: string | null;
  rate: number;
};

export const DEFAULT_SETTINGS: VoiceSettings = {
  enabled: false,
  consented: false,
  silenceMs: 2500,
  allowInterrupt: false,
  voiceName: null,
  rate: 1,
};

export const SILENCE_CHOICES_MS = [1500, 2500, 4000] as const;

const KEY = "cyntra:voice";

const clamp = (n: unknown, lo: number, hi: number, fallback: number) =>
  typeof n === "number" && Number.isFinite(n) ? Math.min(hi, Math.max(lo, n)) : fallback;

/** Anything stored is untrusted input: validate field by field. */
export function sanitizeSettings(raw: unknown): VoiceSettings {
  const r = (raw && typeof raw === "object" ? raw : {}) as Record<string, unknown>;
  return {
    enabled: r.enabled === true,
    consented: r.consented === true,
    silenceMs: clamp(r.silenceMs, 1000, 6000, DEFAULT_SETTINGS.silenceMs),
    allowInterrupt: r.allowInterrupt === true,
    voiceName: typeof r.voiceName === "string" && r.voiceName.length < 200 ? r.voiceName : null,
    rate: clamp(r.rate, 0.7, 1.4, DEFAULT_SETTINGS.rate),
  };
}

type StorageLike = Pick<Storage, "getItem" | "setItem">;

export function loadSettings(storage?: StorageLike): VoiceSettings {
  try {
    const s = storage ?? window.localStorage;
    const raw = s.getItem(KEY);
    return raw ? sanitizeSettings(JSON.parse(raw)) : DEFAULT_SETTINGS;
  } catch {
    return DEFAULT_SETTINGS;
  }
}

export function saveSettings(settings: VoiceSettings, storage?: StorageLike): void {
  try {
    (storage ?? window.localStorage).setItem(KEY, JSON.stringify(settings));
  } catch {
    // storage unavailable (private mode, blocked): settings just aren't remembered
  }
}
