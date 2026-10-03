// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/utils";
import { ApiError, apiClient } from "@/lib/api-client/fastapi";
import { CodeEditorPanel } from "./CodeEditorPanel";

vi.mock("@/lib/api-client/fastapi", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api-client/fastapi")>()),
  apiClient: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));
vi.mock("@/lib/supabase/client", () => ({ createClient: () => ({}) }));
vi.mock("next-themes", () => ({ useTheme: () => ({ resolvedTheme: "light" }) }));
// Monaco is lazy and heavy: a plain textarea stands in for it.
vi.mock("next/dynamic", () => ({
  default: () =>
    function FakeEditor({ value, onChange }: { value: string; onChange: (v: string) => void }) {
      return <textarea aria-label="Solution code" value={value} onChange={(e) => onChange(e.target.value)} />;
    },
}));

const problem = {
  enabled: true,
  active: true,
  phase: "coding",
  problem_number: 1,
  total_problems: 2,
  question: "Reverse a string.",
  submission: null,
  review_job_id: null,
};

function setup() {
  const onReviewed = vi.fn();
  renderWithProviders(
    <CodeEditorPanel
      interviewId="i1"
      refreshKey="a"
      onBusyChange={vi.fn()}
      onReviewed={onReviewed}
      onProblemChange={vi.fn()}
    />
  );
  return { onReviewed, user: userEvent.setup() };
}

beforeEach(() => {
  window.localStorage.clear();
  vi.mocked(apiClient.get).mockReset();
  vi.mocked(apiClient.post).mockReset();
  vi.mocked(apiClient.get).mockImplementation(async (path: string) => {
    if (path === "/interviews/i1/problem") return problem as never;
    if (path === "/jobs/j1") return { id: "j1", status: "succeeded", progress: null, result: null, error: null } as never;
    throw new Error(`unexpected GET ${path}`);
  });
});

describe("CodeEditorPanel submit flow", () => {
  it("keeps Submit disabled until there is code", async () => {
    const { user } = setup();
    const submit = await screen.findByRole("button", { name: "Submit solution" });
    expect(submit).toBeDisabled();
    await user.type(screen.getByLabelText("Solution code"), "print(1)");
    expect(submit).toBeEnabled();
  });

  it("asks for confirmation, and 'Keep editing' sends nothing", async () => {
    const { user } = setup();
    await user.type(await screen.findByLabelText("Solution code"), "print(1)");
    await user.click(screen.getByRole("button", { name: "Submit solution" }));

    expect(screen.getByRole("group", { name: "Confirm submission" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Keep editing" }));
    expect(apiClient.post).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Submit solution" })).toBeInTheDocument();
  });

  it("submits once confirmed, polls the review job and tells the room", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ job_id: "j1", submission_id: "s1" } as never);
    const { user, onReviewed } = setup();
    await user.type(await screen.findByLabelText("Solution code"), "print(1)");
    await user.click(screen.getByRole("button", { name: "Submit solution" }));
    await user.click(screen.getByRole("button", { name: "Yes, submit" }));

    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith("/interviews/i1/submissions", {
        language: "Python",
        code: "print(1)",
      })
    );
    await waitFor(() => expect(onReviewed).toHaveBeenCalledTimes(1));
  });

  it("shows the error and stays submittable when the submission is rejected", async () => {
    vi.mocked(apiClient.post).mockRejectedValue(new ApiError(409, "You already submitted this problem."));
    const { user } = setup();
    await user.type(await screen.findByLabelText("Solution code"), "print(1)");
    await user.click(screen.getByRole("button", { name: "Submit solution" }));
    await user.click(screen.getByRole("button", { name: "Yes, submit" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("You already submitted");
  });
});
