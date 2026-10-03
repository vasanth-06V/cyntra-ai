// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/utils";
import { ApiError, apiClient } from "@/lib/api-client/fastapi";
import { InterviewRoomView } from "./InterviewRoomView";

const push = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, refresh: vi.fn() }) }));
vi.mock("@/lib/api-client/fastapi", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api-client/fastapi")>()),
  apiClient: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));
vi.mock("@/lib/supabase/client", () => ({ createClient: () => ({}) }));
vi.mock("@/components/interview/CodeEditorPanel", () => ({ CodeEditorPanel: () => null }));
vi.mock("@/lib/voice/useVoice", () => ({
  ERROR_TEXT: {},
  useVoice: () => ({
    supported: false,
    listening: false,
    speaking: false,
    pending: false,
    editing: false,
    caption: "",
    error: null,
    speak: vi.fn(),
    sendNow: vi.fn(),
    stopSpeaking: vi.fn(),
    edit: vi.fn(),
    resume: vi.fn(),
    changeCaption: vi.fn(),
  }),
}));

const interview = (status: string) => ({
  id: "i1",
  type: "behavioral",
  status,
  phase: null,
  provider: "gemini",
  resume_id: null,
  started_at: null,
  ends_at: null,
  created_at: "2026-01-01T00:00:00Z",
});

function load(status: string) {
  vi.mocked(apiClient.get).mockImplementation((async (path: string) => {
    if (path === "/interviews/i1") return interview(status);
    if (path === "/interviews/i1/transcript") return [];
    throw new Error(`unexpected GET ${path}`);
  }) as never);
}

beforeEach(() => {
  push.mockReset();
  vi.mocked(apiClient.get).mockReset();
  vi.mocked(apiClient.post).mockReset();
  vi.mocked(apiClient.delete).mockReset();
});

describe("InterviewRoomView: cancel setup", () => {
  it("offers Cancel setup for an interview that is still setting up, and shows it as stopped", async () => {
    load("setting_up");
    vi.mocked(apiClient.post).mockResolvedValue(interview("aborted") as never);
    const user = userEvent.setup();
    renderWithProviders(<InterviewRoomView interviewId="i1" />);

    await user.click(await screen.findByRole("button", { name: "Cancel setup" }));

    await waitFor(() => expect(apiClient.post).toHaveBeenCalledWith("/interviews/i1/abort"));
    expect(await screen.findByText("This interview was stopped before it finished.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cancel setup" })).not.toBeInTheDocument();
    expect(await screen.findByText("Setup cancelled")).toBeInTheDocument();
  });

  it("reloads when the server says it can no longer be cancelled (409)", async () => {
    load("setting_up");
    vi.mocked(apiClient.post).mockRejectedValue(new ApiError(409, "No longer cancellable", "interview_not_cancellable"));
    const user = userEvent.setup();
    renderWithProviders(<InterviewRoomView interviewId="i1" />);
    await user.click(await screen.findByRole("button", { name: "Cancel setup" }));

    expect(await screen.findByText("This interview is no longer being set up")).toBeInTheDocument();
    await waitFor(() => expect(vi.mocked(apiClient.get).mock.calls.filter(([p]) => p === "/interviews/i1").length).toBeGreaterThan(1));
  });

  it("shows other cancel failures as an error toast and keeps the button", async () => {
    load("setting_up");
    vi.mocked(apiClient.post).mockRejectedValue(new ApiError(500, "abort failed"));
    const user = userEvent.setup();
    renderWithProviders(<InterviewRoomView interviewId="i1" />);
    await user.click(await screen.findByRole("button", { name: "Cancel setup" }));
    expect(await screen.findByText("abort failed")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel setup" })).toBeEnabled();
  });
});

describe("InterviewRoomView: delete", () => {
  it("deletes a finished interview after confirming, then returns to the list", async () => {
    load("completed");
    vi.mocked(apiClient.delete).mockResolvedValue(undefined as never);
    const user = userEvent.setup();
    renderWithProviders(<InterviewRoomView interviewId="i1" />);

    await user.click(await screen.findByRole("button", { name: /Delete interview/ }));
    const dialog = await screen.findByRole("alertdialog", { name: "Delete this interview?" });
    expect(dialog).toHaveTextContent(/transcript/i);
    expect(apiClient.delete).not.toHaveBeenCalled();
    await user.click(within(dialog).getByRole("button", { name: "Delete interview" }));

    await waitFor(() => expect(apiClient.delete).toHaveBeenCalledWith("/interviews/i1"));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/interviews"));
  });

  it("stays in the room and explains when the delete fails", async () => {
    load("aborted");
    vi.mocked(apiClient.delete).mockRejectedValue(new ApiError(500, "delete failed"));
    const user = userEvent.setup();
    renderWithProviders(<InterviewRoomView interviewId="i1" />);
    await user.click(await screen.findByRole("button", { name: /Delete interview/ }));
    await user.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Delete interview" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("delete failed");
    expect(push).not.toHaveBeenCalled();
  });

  it("does not offer delete while the interview is running", async () => {
    load("in_progress");
    renderWithProviders(<InterviewRoomView interviewId="i1" />);
    await screen.findByRole("button", { name: "End interview" });
    expect(screen.queryByRole("button", { name: /Delete interview/ })).not.toBeInTheDocument();
  });
});
