// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/utils";
import { apiClient } from "@/lib/api-client/fastapi";
import { CodeEditorPanel } from "./CodeEditorPanel";

vi.mock("@/lib/api-client/fastapi", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api-client/fastapi")>()),
  apiClient: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));
vi.mock("@/lib/supabase/client", () => ({ createClient: () => ({}) }));
vi.mock("next-themes", () => ({ useTheme: () => ({ resolvedTheme: "light" }) }));
// Monaco's loader fetches its files from a CDN; here that fails (blocked or offline).
vi.mock("@monaco-editor/react", () => ({
  default: () => <div>monaco</div>,
  loader: { init: () => Promise.reject(new Error("CDN blocked")) },
}));

const problem = {
  enabled: true,
  active: true,
  phase: "coding",
  problem_number: 1,
  total_problems: 1,
  question: "Reverse a string.",
  submission: null,
  review_job_id: null,
};

beforeEach(() => {
  window.localStorage.clear();
  vi.mocked(apiClient.get).mockReset().mockImplementation(async (path: string) => {
    if (path === "/interviews/i1/problem") return problem as never;
    throw new Error(`unexpected GET ${path}`);
  });
  vi.mocked(apiClient.post).mockReset().mockResolvedValue({ job_id: "j1", submission_id: "s1" } as never);
});

describe("CodeEditorPanel when the editor cannot load (M-14)", () => {
  it("tells the user, and the plain textarea still works for submitting", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <CodeEditorPanel interviewId="i1" refreshKey="a" onBusyChange={vi.fn()} onReviewed={vi.fn()} onProblemChange={vi.fn()} />
    );
    expect(await screen.findByText(/Editor failed to load/)).toBeInTheDocument();
    const box = screen.getByLabelText("Solution code");
    await user.type(box, "print(1)");
    expect(box).toHaveValue("print(1)");

    // The normal submit flow is untouched.
    await user.click(screen.getByRole("button", { name: "Submit solution" }));
    await user.click(screen.getByRole("button", { name: "Yes, submit" }));
    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith("/interviews/i1/submissions", { language: "Python", code: "print(1)" })
    );
  });
});
