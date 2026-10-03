// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockFetch, renderWithProviders } from "@/test/utils";
import { ApiError, apiClient } from "@/lib/api-client/fastapi";
import { AtsScoreView } from "./AtsScoreView";

vi.mock("@/lib/api-client/fastapi", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api-client/fastapi")>()),
  apiClient: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));
vi.mock("@/lib/supabase/client", () => ({ createClient: () => ({}) }));
vi.mock("@/components/ats/ScoreBreakdown", () => ({
  ScoreBreakdown: ({ result }: { result: { composite_score: number } }) => (
    <p>Composite {result.composite_score}</p>
  ),
}));

const resumes = [{ id: "r1", file_key: "resumes/u/cv.pdf", parsed_text: "x", created_at: "2026-01-01T00:00:00Z" }];
const keys = [{ id: "k", provider: "gemini", slot: "primary", is_valid: true, last_validated_at: null }];

beforeEach(() => {
  // Keys for /keys, an empty history for the "Previous checks" panel.
  vi.mocked(apiClient.get)
    .mockReset()
    .mockImplementation((async (path: string) => (path.startsWith("/ats/history") ? [] : keys)) as never);
  vi.mocked(apiClient.post).mockReset();
});

const JD = "We are hiring a backend engineer who knows Python and Postgres.";

describe("AtsScoreView", () => {
  it("scores a resume against a job description", async () => {
    mockFetch([{ match: "/api/resumes", json: resumes }]);
    vi.mocked(apiClient.post).mockResolvedValue({ composite_score: 81 } as never);
    const user = userEvent.setup();
    renderWithProviders(<AtsScoreView />);

    const submit = await screen.findByRole("button", { name: "Check score" });
    expect(submit).toBeDisabled();
    await user.type(screen.getByLabelText("Job description"), JD);
    expect(submit).toBeEnabled();
    await user.click(submit);

    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith("/ats/score", {
        resume_id: "r1",
        jd_text: JD,
        provider: "gemini",
      })
    );
    expect(await screen.findByText("Composite 81")).toBeInTheDocument();
  });

  it("explains a too-short job description instead of silently disabling the button", async () => {
    mockFetch([{ match: "/api/resumes", json: resumes }]);
    const user = userEvent.setup();
    renderWithProviders(<AtsScoreView />);
    await user.type(await screen.findByLabelText("Job description"), "short");
    expect(screen.getByText(/at least 10 characters/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Check score" })).toBeDisabled();
  });

  it("shows the API error when scoring fails and keeps the form", async () => {
    mockFetch([{ match: "/api/resumes", json: resumes }]);
    vi.mocked(apiClient.post).mockRejectedValue(new ApiError(429, "Too many requests. Wait a minute."));
    const user = userEvent.setup();
    renderWithProviders(<AtsScoreView />);
    await user.type(await screen.findByLabelText("Job description"), JD);
    await user.click(screen.getByRole("button", { name: "Check score" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Too many requests");
    expect(screen.getByLabelText("Job description")).toHaveValue(JD);
    expect(screen.getByRole("button", { name: "Check score" })).toBeEnabled();
  });

  it("shows a load error with retry, not a misleading empty state", async () => {
    mockFetch([{ match: "/api/resumes", status: 401, json: { error: "Not signed in" } }]);
    renderWithProviders(<AtsScoreView />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Not signed in");
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
    expect(screen.queryByText("No processed resume yet")).not.toBeInTheDocument();
  });
});
