// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ScoreBreakdown } from "./ScoreBreakdown";
import type { ScoreResponse } from "@/types/ats";

// Rendered for real (the ATS view tests replace it with a stub).
const result: ScoreResponse = {
  composite_score: 72,
  keyword_score: 0.8,
  semantic_score: 0.65,
  formatting_score: 0.9,
  feedback: "Here are some tips:\n- Add **metrics** to your bullets\n- Mention Docker\n  in a project",
  missing_must_have: ["Kubernetes"],
  missing_nice_to_have: ["Terraform"],
  coverage: [
    { term: "Python", kind: "must", covered: true, strength: 1, section: "Skills", evidence: "Built APIs in\n Python" },
    { term: "Kubernetes", kind: "must", covered: false, strength: 0, section: null, evidence: "" },
    { term: "Docker", kind: "nice", covered: true, strength: 0.6, section: null, evidence: "" },
  ],
};

describe("ScoreBreakdown", () => {
  it("shows the composite score with the matching verdict", () => {
    render(<ScoreBreakdown result={result} />);
    expect(screen.getByText("Composite score")).toBeInTheDocument();
    expect(screen.getByText("Good match, some gaps")).toBeInTheDocument();
    expect(screen.getByText("out of 100")).toBeInTheDocument();
  });

  it.each([
    [85, "Strong match"],
    [60, "Good match, some gaps"],
    [45, "Partial match"],
    [10, "Weak match"],
  ])("labels a score of %i as %s", (score, label) => {
    render(<ScoreBreakdown result={{ ...result, composite_score: score }} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it("lists the three sub-scores as percentages", () => {
    render(<ScoreBreakdown result={result} />);
    expect(screen.getByText("Keyword match").nextSibling).toHaveTextContent("80%");
    expect(screen.getByText("Semantic relevance").nextSibling).toHaveTextContent("65%");
    expect(screen.getByText("Formatting").nextSibling).toHaveTextContent("90%");
  });

  it("turns the model's feedback into clean numbered tips", () => {
    render(<ScoreBreakdown result={result} />);
    const tips = screen.getByRole("heading", { name: "How to improve" }).parentElement!;
    expect(within(tips).getAllByRole("listitem")).toHaveLength(2);
    expect(within(tips).getByText("Add metrics to your bullets")).toBeInTheDocument();
    expect(within(tips).getByText("Mention Docker in a project")).toBeInTheDocument();
  });

  it("says so when there are no suggestions", () => {
    render(<ScoreBreakdown result={{ ...result, feedback: "" }} />);
    expect(screen.getByText("No suggestions this time.")).toBeInTheDocument();
  });

  it("shows missing must-have and nice-to-have keywords, and hides the card when none are missing", () => {
    const { rerender } = render(<ScoreBreakdown result={result} />);
    const missing = screen.getByRole("heading", { name: "Missing keywords" }).parentElement!;
    expect(within(missing).getByText("Must-have")).toBeInTheDocument();
    expect(within(missing).getByText("Kubernetes")).toBeInTheDocument();
    expect(within(missing).getByText("Nice-to-have")).toBeInTheDocument();
    expect(within(missing).getByText("Terraform")).toBeInTheDocument();

    rerender(<ScoreBreakdown result={{ ...result, missing_must_have: [], missing_nice_to_have: [] }} />);
    expect(screen.queryByRole("heading", { name: "Missing keywords" })).not.toBeInTheDocument();
  });

  it("groups requirement coverage and reveals evidence for a covered requirement", async () => {
    const user = userEvent.setup();
    render(<ScoreBreakdown result={result} />);
    const card = screen.getByRole("heading", { name: "Requirements from the job description" }).parentElement!;
    expect(within(card).getByText("1 of 2 covered")).toBeInTheDocument(); // must-have group
    expect(within(card).getByText("1 of 1 covered")).toBeInTheDocument(); // nice-to-have group
    expect(within(card).getAllByRole("img", { name: "Covered" })).toHaveLength(2);
    expect(within(card).getAllByRole("img", { name: "Not covered" })).toHaveLength(1);
    expect(within(card).getByText("· Skills")).toBeInTheDocument();

    const python = within(card).getByText("Python").closest("details")!;
    expect(python).not.toHaveAttribute("open");
    await user.click(within(python).getByText("Python"));
    expect(python).toHaveAttribute("open");
    expect(within(python).getByText("Built APIs in Python")).toBeInTheDocument();

    // A requirement that is not covered (or has no evidence) is a plain row, not a disclosure.
    expect(within(card).getByText("Kubernetes").closest("details")).toBeNull();
  });

  it("omits the requirements card for results saved before coverage existed", () => {
    render(<ScoreBreakdown result={{ ...result, coverage: undefined }} />);
    expect(screen.queryByText("Requirements from the job description")).not.toBeInTheDocument();
  });
});
