/**
 * Decides when a spoken answer is finished.
 *
 * Browsers end a recognition session on their own after a few seconds of
 * quiet, so one answer can span several sessions. This buffer keeps what was
 * heard across sessions and fires `onReady` once there has been no new speech
 * for `silenceMs`. Pure logic with injectable timers, so it is unit-tested with
 * a fake clock.
 */

export type Timers = {
  set: (fn: () => void, ms: number) => unknown;
  clear: (id: unknown) => void;
};

export const realTimers: Timers = {
  set: (fn, ms) => setTimeout(fn, ms),
  clear: (id) => clearTimeout(id as ReturnType<typeof setTimeout>),
};

const join = (a: string, b: string) => [a, b].filter(Boolean).join(" ");

export class UtteranceBuffer {
  private base = ""; // text from earlier recognition sessions of this answer
  private current = ""; // the running session's transcript (final + interim)
  private timer: unknown = null;

  constructor(
    private silenceMs: number,
    private readonly onReady: (text: string) => void,
    private readonly timers: Timers = realTimers
  ) {}

  get text(): string {
    return join(this.base, this.current);
  }

  setSilenceMs(ms: number): void {
    this.silenceMs = ms;
  }

  /** The recognizer's full transcript for the running session. Returns the whole caption. */
  update(sessionText: string): string {
    this.current = sessionText.trim();
    this.rearm();
    return this.text;
  }

  /** The session ended (browsers do this on their own): keep what was heard. */
  endSession(): void {
    if (this.current) {
      this.base = join(this.base, this.current);
      this.current = "";
    }
  }

  /** The candidate edited the caption by hand: that is now the answer. */
  setText(text: string): void {
    this.clearTimer();
    this.base = text.trim();
    this.current = "";
  }

  reset(): void {
    this.clearTimer();
    this.base = "";
    this.current = "";
  }

  dispose(): void {
    this.reset();
  }

  private clearTimer(): void {
    if (this.timer !== null) {
      this.timers.clear(this.timer);
      this.timer = null;
    }
  }

  private rearm(): void {
    this.clearTimer();
    if (!this.text) return;
    this.timer = this.timers.set(() => {
      this.timer = null;
      const text = this.text;
      if (text) this.onReady(text);
    }, this.silenceMs);
  }
}
