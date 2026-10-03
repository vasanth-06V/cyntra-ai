import { describe, expect, it } from "vitest";
import type { ReportData } from "@/types/reports";
import { reportToMarkdown, resultLabel, timeLeft } from "./format";

const HOUR = 3_600_000;
const NOW = Date.parse("2026-10-03T12:00:00Z");
const at = (ms: number) => new Date(NOW + ms).toISOString();

describe("timeLeft (the 7-day countdown)", () => {
  it("counts down in days and hours", () => {
    expect(timeLeft(at(7 * 24 * HOUR - 1000), NOW)).toBe("6 days 23 hours left");
    expect(timeLeft(at(2 * 24 * HOUR), NOW)).toBe("2 days left");
    expect(timeLeft(at(24 * HOUR), NOW)).toBe("1 day left");
    expect(timeLeft(at(5 * HOUR), NOW)).toBe("5 hours left");
    expect(timeLeft(at(HOUR), NOW)).toBe("1 hour left");
    expect(timeLeft(at(30 * 60_000), NOW)).toBe("under an hour left");
  });

  it("is expired at exactly the deadline and after it", () => {
    expect(timeLeft(at(0), NOW)).toBe("Expired");
    expect(timeLeft(at(-HOUR), NOW)).toBe("Expired");
    expect(timeLeft("not a date", NOW)).toBe("Expired");
  });
});

const REPORT: ReportData = {
  version: 1,
  interview: { id: "i-1", type: "coding", started_at: null, minutes_used: 55 },
  overall_score: 72,
  band: "Good",
  verdict: "Solid fundamentals.",
  dimensions: [
    { key: "communication", label: "Communication", score: 4, reason: "Clear.", quote: "I would use a hash map" },
    { key: "structure", label: "Structure and clarity", score: 3, reason: "Mostly organised.", quote: null },
  ],
  strengths: [{ point: "Good intuition", quote: null }],
  improvements: [{ point: "State complexity earlier", quote: "it is probably fine" }],
  phase_notes: [{ phase: "problem_1", note: "Found the optimal idea." }],
  next_steps: ["Practice complexity analysis"],
  coding: [
    {
      problem: 1, language: "Python", line_count: 12, result: "mostly_correct", approach: "different_but_valid",
      issues: ["Quadratic time"], edge_cases_missed: ["empty input"], candidate_complexity: "O(n^2)", reference_complexity: "O(n)",
    },
  ],
  stats: { answers: 9, avg_words: 40, phases: [], omitted_turns: 0 },
  disclaimer: "AI-generated guidance.",
};

describe("reportToMarkdown", () => {
  const md = reportToMarkdown(REPORT, { typeLabel: "Coding", createdAt: at(0), expiresAt: at(7 * 24 * HOUR) });

  it("has the score, the skills with quotes and the lists", () => {
    expect(md).toContain("# Interview report — Coding");
    expect(md).toContain("## Overall: 72/100 (Good)");
    expect(md).toContain("- **Communication: 4/5** — Clear. _“I would use a hash map”_");
    expect(md).toContain("- **Structure and clarity: 3/5** — Mostly organised.");
    expect(md).toContain("- State complexity earlier _“it is probably fine”_");
    expect(md).toContain("- **problem 1**: Found the optimal idea.");
    expect(md).toContain("- Practice complexity analysis");
  });

  it("includes the coding round from the stored review", () => {
    expect(md).toContain("### Problem 1 — Python, 12 lines — Mostly correct");
    expect(md).toContain("Approach: different but valid");
    expect(md).toContain("Complexity: yours O(n^2); reference O(n)");
    expect(md).toContain("- Issue: Quadratic time");
    expect(md).toContain("- Missed edge case: empty input");
  });

  it("ends with the disclaimer and omits empty sections", () => {
    expect(md.trim().endsWith("_AI-generated guidance._")).toBe(true);
    const bare = reportToMarkdown({ ...REPORT, coding: [], strengths: [], improvements: [], phase_notes: [], next_steps: [] }, {
      typeLabel: "HR", createdAt: at(0), expiresAt: at(HOUR),
    });
    for (const heading of ["Coding round", "What went well", "What to improve", "Phase by phase", "Next steps"]) {
      expect(bare).not.toContain(heading);
    }
  });

  it("labels results", () => {
    expect(resultLabel("incorrect")).toBe("Incorrect");
    expect(resultLabel("unknown")).toBe("unknown");
  });
});
