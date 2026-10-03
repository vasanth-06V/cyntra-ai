// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockFetch, renderWithProviders } from "@/test/utils";
import { ApiError, apiClient } from "@/lib/api-client/fastapi";
import { AtsScoreView } from "./AtsScoreView";

vi.mock("@/lib/api-client/fastapi", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api-client/fastapi")>()),
  apiClient: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));
vi.mock("@/lib/supabase/client", () => ({ createClient: () => ({}) }));
vi.mock("@/components/ats/ScoreBreakdown", () => ({
  ScoreBreakdown: ({ result }: { result: { composite_score: number } }) => <p>Composite {result.composite_score}</p>,
}));

const resumes = [{ id: "r1", file_key: "resumes/u/cv.pdf", parsed_text: "x", created_at: "2026-01-01T00:00:00Z" }];
const keys = [{ id: "k", provider: "gemini", slot: "primary", is_valid: true, last_validated_at: null }];
const JD = "We are hiring a backend engineer who knows Python and Postgres.";

const item = (n: number, over: Record<string, unknown> = {}) => ({
  id: `h${n}`,
  resume_id: "r1",
  job_title: `Role ${n}`,
  jd_excerpt: `We need a person who does thing ${n}`,
  provider: "gemini",
  composite_score: 60 + n,
  created_at: "2026-01-05T10:00:00Z",
  ...over,
});
const detail = (n: number) => ({
  ...item(n),
  result: {
    composite_score: 60 + n,
    keyword_score: 0.5,
    semantic_score: 0.5,
    formatting_score: 0.5,
    feedback: "",
    missing_must_have: [],
    missing_nice_to_have: [],
    coverage: [],
  },
});

/** Routes apiClient.get: `extra` may answer (or throw for) a path first; history list and keys otherwise. */
function history(list: unknown[], extra?: (path: string) => unknown) {
  vi.mocked(apiClient.get).mockImplementation((async (path: string) => {
    const custom = extra?.(path);
    if (custom !== undefined) return custom;
    if (path.startsWith("/ats/history?")) return list;
    return keys;
  }) as never);
}

beforeEach(() => {
  vi.mocked(apiClient.post).mockReset();
  vi.mocked(apiClient.delete).mockReset();
  mockFetch([{ match: "/api/resumes", json: resumes }]);
});

describe("ATS previous checks", () => {
  it("lists the saved checks for the selected resume and says how many are kept", async () => {
    history([item(1), item(2, { job_title: null })]);
    renderWithProviders(<AtsScoreView />);

    expect(await screen.findByRole("button", { name: /Open saved check: Role 1/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Open saved check: Untitled role/ })).toBeInTheDocument();
    expect(screen.getByText(/We need a person who does thing 1/)).toBeInTheDocument();
    expect(screen.getByText(/last 10 checks per resume are kept/i)).toBeInTheDocument();
    expect(apiClient.get).toHaveBeenCalledWith("/ats/history?resume_id=r1&limit=10");
  });

  it("shows an empty state when there are none", async () => {
    history([]);
    renderWithProviders(<AtsScoreView />);
    expect(await screen.findByText("No previous checks yet")).toBeInTheDocument();
  });

  it("shows an error with a working retry", async () => {
    history([], (path) => {
      if (path.startsWith("/ats/history?")) throw new ApiError(500, "history is down");
    });
    const user = userEvent.setup();
    renderWithProviders(<AtsScoreView />);
    expect(await screen.findByText("history is down")).toBeInTheDocument();

    history([item(1)]);
    await user.click(screen.getByRole("button", { name: /try again/i }));
    expect(await screen.findByRole("button", { name: /Open saved check: Role 1/ })).toBeInTheDocument();
  });

  it("opens a saved result in the breakdown with a banner, and returns to a new check", async () => {
    history([item(1)], (path) => (path === "/ats/history/h1" ? detail(1) : undefined));
    const user = userEvent.setup();
    renderWithProviders(<AtsScoreView />);

    await user.click(await screen.findByRole("button", { name: /Open saved check: Role 1/ }));
    expect(await screen.findByText("Composite 61")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(/Saved result from/);
    expect(screen.getByText("Showing")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Run a new check/ }));
    expect(screen.queryByText("Composite 61")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Job description")).toHaveFocus();
  });

  it("reports a failure to open a saved result with a toast", async () => {
    history([item(1)], (path) => {
      if (path === "/ats/history/h1") throw new ApiError(404, "That check no longer exists.");
    });
    const user = userEvent.setup();
    renderWithProviders(<AtsScoreView />);
    await user.click(await screen.findByRole("button", { name: /Open saved check: Role 1/ }));
    expect(await screen.findByText("That check no longer exists.")).toBeInTheDocument();
  });

  it("deletes a saved check after confirming, with a toast, and clears it if it was open", async () => {
    history([item(1), item(2)], (path) => (path === "/ats/history/h1" ? detail(1) : undefined));
    vi.mocked(apiClient.delete).mockResolvedValue(undefined as never);
    const user = userEvent.setup();
    renderWithProviders(<AtsScoreView />);

    await user.click(await screen.findByRole("button", { name: /Open saved check: Role 1/ }));
    await screen.findByText("Composite 61");

    await user.click(screen.getByRole("button", { name: "Delete saved check: Role 1" }));
    const dialog = await screen.findByRole("alertdialog", { name: "Delete this saved check?" });
    expect(apiClient.delete).not.toHaveBeenCalled();
    await user.click(within(dialog).getByRole("button", { name: "Delete check" }));

    await waitFor(() => expect(apiClient.delete).toHaveBeenCalledWith("/ats/history/h1"));
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: /Open saved check: Role 1/ })).not.toBeInTheDocument()
    );
    expect(screen.getByRole("button", { name: /Open saved check: Role 2/ })).toBeInTheDocument();
    expect(await screen.findByText("Saved check deleted")).toBeInTheDocument();
    expect(screen.queryByText("Composite 61")).not.toBeInTheDocument();
  });

  it("keeps the row and shows the error in the dialog when delete fails", async () => {
    history([item(1)]);
    vi.mocked(apiClient.delete).mockRejectedValue(new ApiError(500, "could not delete"));
    const user = userEvent.setup();
    renderWithProviders(<AtsScoreView />);
    await user.click(await screen.findByRole("button", { name: "Delete saved check: Role 1" }));
    await user.click(await screen.findByRole("button", { name: "Delete check" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("could not delete");
    expect(screen.getByRole("button", { name: /Open saved check: Role 1/ })).toBeInTheDocument();
  });

  it("refetches the list after a new score, also when history_id is null", async () => {
    let list: unknown[] = [];
    history([], (path) => (path.startsWith("/ats/history?") ? list : undefined));
    vi.mocked(apiClient.post).mockResolvedValue({ composite_score: 81, history_id: null } as never);
    const user = userEvent.setup();
    renderWithProviders(<AtsScoreView />);
    await screen.findByText("No previous checks yet");

    list = [item(5)];
    await user.type(screen.getByLabelText("Job description"), JD);
    await user.click(screen.getByRole("button", { name: "Check score" }));

    expect(await screen.findByRole("button", { name: /Open saved check: Role 5/ })).toBeInTheDocument();
    expect(screen.getByText("Composite 81")).toBeInTheDocument();
  });

  it("marks the new check as showing when history_id comes back", async () => {
    let list: unknown[] = [];
    history([], (path) => (path.startsWith("/ats/history?") ? list : undefined));
    vi.mocked(apiClient.post).mockResolvedValue({ composite_score: 66, history_id: "h6" } as never);
    const user = userEvent.setup();
    renderWithProviders(<AtsScoreView />);
    await screen.findByText("No previous checks yet");

    list = [item(6)];
    await user.type(screen.getByLabelText("Job description"), JD);
    await user.click(screen.getByRole("button", { name: "Check score" }));
    expect(await screen.findByText("Showing")).toBeInTheDocument();
  });
});
