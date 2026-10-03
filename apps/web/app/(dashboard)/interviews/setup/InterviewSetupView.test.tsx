// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockFetch, renderWithProviders } from "@/test/utils";
import { ApiError, apiClient } from "@/lib/api-client/fastapi";
import { InterviewSetupView } from "./InterviewSetupView";

const push = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, refresh: vi.fn() }) }));
vi.mock("@/lib/api-client/fastapi", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api-client/fastapi")>()),
  apiClient: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));
vi.mock("@/lib/supabase/client", () => ({ createClient: () => ({}) }));
vi.mock("@/components/three/LoadingScene", () => ({ LoadingScene: () => null }));

const resumes = [
  { id: "r1", file_key: "resumes/u/cv.pdf", display_name: "Backend CV", parsed_text: "x", created_at: "2026-01-01T00:00:00Z" },
];
const keys = [{ id: "k", provider: "gemini", slot: "primary", is_valid: true, last_validated_at: null }];
const JD = "We are hiring a backend engineer who knows Python and Postgres.";

beforeEach(() => {
  push.mockReset();
  mockFetch([{ match: "/api/resumes", json: resumes }]);
  vi.mocked(apiClient.get)
    .mockReset()
    .mockImplementation((async (path: string) => {
      if (path === "/keys") return keys;
      if (path === "/jobs/j1") return { id: "j1", kind: "setup", status: "running", progress: "Picking questions", result: null, error: null };
      throw new Error(`unexpected GET ${path}`);
    }) as never);
  vi.mocked(apiClient.post).mockReset();
});

async function startSetup() {
  const user = userEvent.setup();
  renderWithProviders(<InterviewSetupView />);
  await user.type(await screen.findByLabelText("Job description"), JD);
  await user.click(screen.getByRole("button", { name: "Start interview" }));
  await screen.findByText("Setting up your interview…");
  return user;
}

describe("InterviewSetupView", () => {
  it("names the resume by its display name in the dropdown", async () => {
    renderWithProviders(<InterviewSetupView />);
    expect(await screen.findByRole("option", { name: "Backend CV" })).toBeInTheDocument();
  });

  it("cancels a setup in progress: aborts the interview, toasts and returns to the form", async () => {
    vi.mocked(apiClient.post).mockImplementation((async (path: string) => {
      if (path === "/interviews") return { job_id: "j1", interview_id: "i1" };
      if (path === "/interviews/i1/abort") return { id: "i1", status: "aborted" };
      throw new Error(`unexpected POST ${path}`);
    }) as never);
    const user = await startSetup();
    await screen.findByText("Picking questions");

    await user.click(screen.getByRole("button", { name: "Cancel" }));

    await waitFor(() => expect(apiClient.post).toHaveBeenCalledWith("/interviews/i1/abort"));
    expect(await screen.findByText("Setup cancelled")).toBeInTheDocument();
    expect(await screen.findByLabelText("Job description")).toHaveValue(JD);
    expect(push).not.toHaveBeenCalled();
  });

  it("opens the interview instead when it had already finished setting up (409)", async () => {
    vi.mocked(apiClient.post).mockImplementation((async (path: string) => {
      if (path === "/interviews") return { job_id: "j1", interview_id: "i1" };
      throw new ApiError(409, "Too late to cancel.", "interview_not_cancellable");
    }) as never);
    const user = await startSetup();
    await screen.findByText("Picking questions");

    await user.click(screen.getByRole("button", { name: "Cancel" }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/interviews/i1"));
  });

  it("tells the user when the cancel call fails and still returns to the form", async () => {
    vi.mocked(apiClient.post).mockImplementation((async (path: string) => {
      if (path === "/interviews") return { job_id: "j1", interview_id: "i1" };
      throw new ApiError(500, "abort failed");
    }) as never);
    const user = await startSetup();
    await screen.findByText("Picking questions");

    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(await screen.findByText("abort failed")).toBeInTheDocument();
    expect(await screen.findByLabelText("Job description")).toBeInTheDocument();
  });
});
