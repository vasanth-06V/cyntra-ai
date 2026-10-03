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
  apiClient: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));
vi.mock("@/lib/supabase/client", () => ({ createClient: () => ({}) }));
// Monaco, speech recognition and speech synthesis are not part of what these tests exercise.
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

const interview = (over: Record<string, unknown> = {}) => ({
  id: "i1",
  type: "behavioral",
  status: "in_progress",
  phase: "intro",
  provider: "gemini",
  resume_id: "r1",
  started_at: "2026-01-01T00:00:00Z",
  ends_at: new Date(Date.now() + 50 * 60_000).toISOString(),
  created_at: "2026-01-01T00:00:00Z",
  ...over,
});

const transcript = [
  { id: "t1", turn_index: 0, speaker: "ai", text: "Welcome. Tell me about yourself.", created_at: "2026-01-01T00:00:00Z" },
];

function load(status = "in_progress") {
  vi.mocked(apiClient.get).mockImplementation(async (path: string) => {
    if (path === "/interviews/i1") return interview({ status }) as never;
    if (path === "/interviews/i1/transcript") return transcript as never;
    throw new Error(`unexpected GET ${path}`);
  });
}

beforeEach(() => {
  push.mockReset();
  vi.mocked(apiClient.get).mockReset();
  vi.mocked(apiClient.post).mockReset();
});

describe("InterviewRoomView", () => {
  it("sends an answer to the turn endpoint and shows the interviewer's reply", async () => {
    load();
    vi.mocked(apiClient.post).mockResolvedValue({
      message: "Great. Why this role?",
      phase: "intro",
      minutes_remaining: 49,
      is_final_phase: false,
    } as never);
    const user = userEvent.setup();
    renderWithProviders(<InterviewRoomView interviewId="i1" />);

    await screen.findByText("Welcome. Tell me about yourself.");
    await user.type(screen.getByLabelText("Your answer"), "I build backends.");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(apiClient.post).toHaveBeenCalledWith("/interviews/i1/turns", { content: "I build backends." });
    const log = screen.getByRole("log");
    expect(await within(log).findByText("Great. Why this role?")).toBeInTheDocument();
    expect(within(log).getByText("I build backends.")).toBeInTheDocument();
  });

  it("sends on Enter, and Shift+Enter keeps writing", async () => {
    load();
    vi.mocked(apiClient.post).mockResolvedValue({ message: "ok", phase: "intro", minutes_remaining: 40, is_final_phase: false } as never);
    const user = userEvent.setup();
    renderWithProviders(<InterviewRoomView interviewId="i1" />);
    const box = await screen.findByLabelText("Your answer");

    await user.type(box, "first{Shift>}{Enter}{/Shift}second");
    expect(apiClient.post).not.toHaveBeenCalled();
    await user.keyboard("{Enter}");
    await waitFor(() => expect(apiClient.post).toHaveBeenCalledWith("/interviews/i1/turns", { content: "first\nsecond" }));
  });

  it("gives the draft back and shows the error when a turn fails", async () => {
    load();
    vi.mocked(apiClient.post).mockRejectedValue(new ApiError(503, "The model is busy"));
    const user = userEvent.setup();
    renderWithProviders(<InterviewRoomView interviewId="i1" />);
    await user.type(await screen.findByLabelText("Your answer"), "My answer");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("The model is busy");
    expect(screen.getByLabelText("Your answer")).toHaveValue("My answer");
    expect(within(screen.getByRole("log")).queryByText("My answer")).not.toBeInTheDocument();
  });

  it("asks before ending, and does nothing when cancelled", async () => {
    load();
    const user = userEvent.setup();
    renderWithProviders(<InterviewRoomView interviewId="i1" />);

    await user.click(await screen.findByRole("button", { name: "End interview" }));
    const dialog = await screen.findByRole("alertdialog", { name: "End the interview now?" });
    await user.click(within(dialog).getByRole("button", { name: "Cancel" }));

    await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument());
    expect(apiClient.post).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Your answer")).toBeInTheDocument();
  });

  it("ends the interview once confirmed and offers the report", async () => {
    load();
    vi.mocked(apiClient.post).mockResolvedValue(interview({ status: "completed" }) as never);
    const user = userEvent.setup();
    renderWithProviders(<InterviewRoomView interviewId="i1" />);

    await user.click(await screen.findByRole("button", { name: "End interview" }));
    await user.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "End interview" }));

    await waitFor(() => expect(apiClient.post).toHaveBeenCalledWith("/interviews/i1/complete"));
    expect(await screen.findByRole("button", { name: "Get my report" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Your answer")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Get my report" }));
    expect(push).toHaveBeenCalledWith("/reports");
  });

  it("shows why ending failed and keeps the interview running", async () => {
    load();
    vi.mocked(apiClient.post).mockRejectedValue(new ApiError(500, "Could not close the interview"));
    const user = userEvent.setup();
    renderWithProviders(<InterviewRoomView interviewId="i1" />);

    await user.click(await screen.findByRole("button", { name: "End interview" }));
    await user.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "End interview" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Could not close the interview");
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
  });

  it("offers a retry when the interview cannot be loaded", async () => {
    vi.mocked(apiClient.get).mockRejectedValue(new ApiError(500, "Interview service is down"));
    renderWithProviders(<InterviewRoomView interviewId="i1" />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Interview service is down");
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });
});
