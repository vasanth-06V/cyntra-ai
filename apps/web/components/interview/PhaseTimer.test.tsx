// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { PhaseTimer } from "./PhaseTimer";

describe("PhaseTimer", () => {
  it("formats minutes and zero-padded seconds and humanises the phase name", () => {
    render(<PhaseTimer phase="technical_deep_dive" minutesRemaining={12.5} />);
    expect(screen.getByText("technical deep dive")).toBeInTheDocument();
    expect(screen.getByRole("timer")).toHaveTextContent("12:30 remaining");
  });

  it("pads single-digit seconds", () => {
    render(<PhaseTimer phase="intro" minutesRemaining={9 + 5 / 60} />);
    expect(screen.getByRole("timer")).toHaveTextContent("9:05");
  });

  it("shows 0:00 when time has run out and never goes negative", () => {
    render(<PhaseTimer phase="wrap_up" minutesRemaining={0} />);
    expect(screen.getByRole("timer")).toHaveTextContent("0:00");
  });

  it("switches to the warning colour in the last five minutes", () => {
    const { rerender } = render(<PhaseTimer phase="intro" minutesRemaining={20} />);
    expect(screen.getByRole("timer").className).not.toContain("text-destructive");
    rerender(<PhaseTimer phase="intro" minutesRemaining={4.9} />);
    expect(screen.getByRole("timer").className).toContain("text-destructive");
  });
});
